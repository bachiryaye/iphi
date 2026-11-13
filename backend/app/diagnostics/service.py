import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.diagnostics.domain.deterministic import (
    MODEL,
    PROVIDER,
    DiagnosisInput,
    RelatedIncident,
    diagnose,
    evidence_set_hash,
    validate,
)
from app.diagnostics.domain.model import DiagnosticKind, DiagnosticStatus, StoredDiagnostic
from app.diagnostics.repository import DiagnosticRepository
from app.identity.domain import AuditAction, AuditContext
from app.identity.service import AuditedMutations
from app.incidents.domain.model import Incident
from app.incidents.service import IncidentHistory, actor_of
from app.topology.domain import PlatformNotFoundError, PlatformTopology, upstream_ids
from app.topology.service import TopologyService

# Evaluations per role group: with one observation each, at most 40 items (§06.2: <= 50).
KEY_EVALUATIONS = 10
MAX_RELATED = 10
MAX_LISTED = 50

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DiagnosisResult:
    diagnostic: StoredDiagnostic
    created: bool


class DiagnosticsService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        wall: Clock,
        platform_now: Callable[[], datetime],
        topology: TopologyService,
    ) -> None:
        self._session_factory = session_factory
        self._audited = AuditedMutations(session_factory, wall)
        self._platform_now = platform_now
        self._topology = topology

    def diagnose(
        self,
        incident_id: uuid.UUID,
        kind: DiagnosticKind,
        idempotency_key: str | None,
        context: AuditContext,
    ) -> DiagnosisResult:
        """A diagnosis of the incident's stored evidence; only the deterministic kind exists
        before US-08. Idempotent: the same key, or unchanged evidence, returns the stored
        diagnosis instead of a new one."""
        with self._audited.run(context, AuditAction.INCIDENT_DIAGNOSE) as work:
            work.audit.target_type, work.audit.target_id = "incident", str(incident_id)
            work.audit.details["kind"] = kind.value
            history = IncidentHistory(work.session)
            incident = history.lock(incident_id)
            work.audit.platform_time = at = self._platform_now()
            diagnostics = DiagnosticRepository(work.session)
            if idempotency_key is not None:
                existing = diagnostics.by_key(incident_id, idempotency_key)
                if existing is not None:
                    work.audit.details["reused"] = str(existing.id)
                    return DiagnosisResult(existing, created=False)
            data = self._input(history, incident)
            digest = evidence_set_hash(data)
            latest = diagnostics.latest(incident_id, DiagnosticKind.DETERMINISTIC)
            if (
                idempotency_key is None
                and latest is not None
                and latest.evidence_set_hash == digest
            ):
                work.audit.details["reused"] = str(latest.id)
                return DiagnosisResult(latest, created=False)
            diagnosis, report = validate(diagnose(data), {i.stored.id for i in data.evidence})
            stored = StoredDiagnostic(
                id=uuid.uuid7(),
                incident_id=incident_id,
                kind=DiagnosticKind.DETERMINISTIC,
                provider=PROVIDER,
                model=MODEL,
                status=DiagnosticStatus.SUCCEEDED,
                diagnosis=diagnosis,
                evidence_set_hash=digest,
                validation=report,
                created_by=context.actor_label,
                created_at=at,
            )
            diagnostics.add(stored, idempotency_key)
            history.record_diagnostic(
                incident, (stored.id, stored.kind.value), actor_of(context), at
            )
            work.audit.details["diagnostic_id"] = str(stored.id)
        log.info("diagnostic.created", incident_id=incident_id, diagnostic_id=stored.id)
        return DiagnosisResult(stored, created=True)

    def of_incident(self, incident_id: uuid.UUID) -> list[StoredDiagnostic]:
        with self._session_factory() as session:
            IncidentHistory(session).find(incident_id)
            return DiagnosticRepository(session).of_incident(incident_id, MAX_LISTED)

    def _input(self, history: IncidentHistory, incident: Incident) -> DiagnosisInput:
        topology = self._platform(incident.platform_id)
        keys = topology.keys_by_id()
        upstream = upstream_ids(incident.component_id, topology.dependencies)
        end = incident.resolved_at or incident.last_seen_at
        related = [
            RelatedIncident(
                r, keys[r.component_id], len(upstream_ids(r.component_id, topology.dependencies))
            )
            for r in history.related(upstream, incident.opened_at, end, MAX_RELATED)
        ]
        return DiagnosisInput(
            incident=incident,
            component_keys=keys,
            evidence=history.key_evidence(incident.id, KEY_EVALUATIONS),
            impacted=[keys[i.component_id] for i in history.impacts(incident.id)],
            related=related,
            logs_attached=history.has_log_evidence(incident.id),
        )

    def _platform(self, platform_id: uuid.UUID) -> PlatformTopology:
        found = next((t for t in self._topology.platforms() if t.platform_id == platform_id), None)
        if found is None:
            raise PlatformNotFoundError(f"No platform {platform_id}.")
        return found
