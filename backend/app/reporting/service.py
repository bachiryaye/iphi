import time
import uuid
from threading import Lock

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.diagnostics.service import DiagnosticReader
from app.incidents.service import IncidentHistory
from app.reporting.csv import csv_report
from app.reporting.domain import (
    ReportBusyError,
    ReportFile,
    ReportFormat,
    ReportRenderer,
    ReportSnapshot,
    ReportTooLargeError,
)
from app.topology.domain import PlatformNotFoundError
from app.topology.service import TopologyService

MAX_REPORT_ITEMS = 1000
MAX_FILE_BYTES = 8_000_000
log = structlog.get_logger(__name__)


class ReportingService:
    def __init__(
        self,
        factory: sessionmaker[Session],
        clock: Clock,
        topology: TopologyService,
        renderer: ReportRenderer,
    ) -> None:
        self._factory, self._clock = factory, clock
        self._topology, self._renderer = topology, renderer
        self._pdf_lock = Lock()

    def snapshot(self, incident_id: uuid.UUID) -> ReportSnapshot:
        with self._factory.begin() as session:
            # No incident locks, and the snapshot transaction ends before rendering.
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            facts = IncidentHistory(session).snapshot(incident_id, MAX_REPORT_ITEMS)
            if max(facts.summary.evidence_count, facts.event_count) > MAX_REPORT_ITEMS:
                raise ReportTooLargeError(
                    f"Reports support up to {MAX_REPORT_ITEMS} evidence items and events each. "
                    "Use the paginated incident evidence and events API for this incident."
                )
            diagnostics = DiagnosticReader(session).for_report(incident_id)
        platform = next(
            (
                p
                for p in self._topology.platforms()
                if p.platform_id == facts.summary.incident.platform_id
            ),
            None,
        )
        if platform is None:
            raise PlatformNotFoundError("The incident platform is unavailable.")
        return ReportSnapshot(facts, diagnostics, platform, self._clock.now())

    def export(self, incident_id: uuid.UUID, format: ReportFormat) -> ReportFile:
        started = time.perf_counter()
        acquired = format is ReportFormat.PDF and self._pdf_lock.acquire(blocking=False)
        if format is ReportFormat.PDF and not acquired:
            raise ReportBusyError("A PDF is being generated. Retry shortly; monitoring continues.")
        try:
            snapshot = self.snapshot(incident_id)
            content = (
                self._renderer.pdf(snapshot) if format is ReportFormat.PDF else csv_report(snapshot)
            )
            if len(content) > MAX_FILE_BYTES:
                raise ReportTooLargeError("The report exceeds the 8 MB download limit.")
        finally:
            if acquired:
                self._pdf_lock.release()
        log.info(
            "report.generated",
            incident_id=incident_id,
            format=format.value,
            size_bytes=len(content),
            duration_ms=round((time.perf_counter() - started) * 1000),
            source="simulation",
        )
        return ReportFile(
            content,
            "application/pdf" if format is ReportFormat.PDF else "text/csv",
            f"IPHI-{snapshot.facts.summary.incident.reference}-simulated.{format.value}",
        )
