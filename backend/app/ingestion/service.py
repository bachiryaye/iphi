import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.connectors.domain import CollectionRequest, CollectionResult, Connector
from app.core.clock import Clock
from app.core.observation import SAMPLE_INTERVAL_S, ObservationSource
from app.core.retention import EvidenceHolds
from app.ingestion.domain.catalog import METRIC_CATALOG, MetricDefinition
from app.ingestion.domain.collection import (
    CollectionOutcome,
    CollectionRun,
    CollectionStatus,
)
from app.ingestion.domain.errors import MetricNotFoundError, PlatformNotSeededError
from app.ingestion.domain.logs import LogQuery, StoredLog
from app.ingestion.domain.observations import ObservationMark, SampleDetail, StoredSample
from app.ingestion.domain.series import (
    Series,
    SeriesQuery,
    find_gaps,
)
from app.ingestion.domain.validation import (
    IngestionPolicy,
    ValidatedBatch,
    ValidationContext,
    validate,
)
from app.ingestion.repository import (
    CollectionCursorRepository,
    CollectionRunRepository,
    MetricCatalogRepository,
    ObservationRepository,
)
from app.topology.domain import ComponentNotFoundError
from app.topology.service import TopologyService

MAX_REJECTION_EXAMPLES = 5

log = structlog.get_logger(__name__)


class _PlatformComponents:
    """Component index of the seeded platform; components only change at seed time."""

    def __init__(self, topology: TopologyService, platform_key: str) -> None:
        self._topology_service = topology
        self._platform_key = platform_key
        self._ids_by_key: dict[str, uuid.UUID] | None = None
        self._keys_by_id: dict[uuid.UUID, str] = {}

    def ids_by_key(self) -> dict[str, uuid.UUID]:
        if self._ids_by_key is None:
            topology = self._topology_service.platform(self._platform_key)
            if topology is None:
                raise PlatformNotSeededError(
                    f"Platform {self._platform_key} is not seeded; run the bootstrap."
                )
            self._ids_by_key = {c.key: c.id for c in topology.components}
            self._keys_by_id = topology.keys_by_id()
        return self._ids_by_key

    def key_of(self, component_id: uuid.UUID) -> str:
        self.ids_by_key()
        key = self._keys_by_id.get(component_id)
        if key is None:
            raise ComponentNotFoundError(f"No component {component_id}.")
        return key


class MetricCatalogService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def ensure(self) -> None:
        """Idempotent seed of `metric_definition` from the code-defined catalog."""
        with self._session_factory.begin() as session:
            MetricCatalogRepository(session).upsert(METRIC_CATALOG)
        log.info("metric_catalog.seeded", metrics=len(METRIC_CATALOG))

    def definitions(self) -> list[MetricDefinition]:
        with self._session_factory() as session:
            return MetricCatalogRepository(session).all()


class CollectionService:
    """Cycle steps 2-3 (architecture §02.2), inside the caller's unit of work.

    Each connector is isolated twice: an exception from the connector is recorded as a failed
    run, and its writes sit in a savepoint so a rejected insert cannot abort the cycle.
    """

    def __init__(
        self,
        connectors: Sequence[Connector],
        topology: TopologyService,
        platform_key: str,
        policy: IngestionPolicy,
        wall: Clock,
    ) -> None:
        self._connectors = tuple(connectors)
        self._components = _PlatformComponents(topology, platform_key)
        self._policy = policy
        self._wall = wall
        self._catalog: dict[str, MetricDefinition] | None = None

    def collect(self, session: Session, platform_now: datetime) -> list[CollectionRun]:
        return [self._collect_one(session, c, platform_now) for c in self._connectors]

    def _collect_one(
        self, session: Session, connector: Connector, platform_now: datetime
    ) -> CollectionRun:
        started_at = self._wall.now()
        request = CollectionRequest(
            platform_now,
            resume_after=CollectionCursorRepository(session).get(connector.key),
            not_before=platform_now - self._policy.late_tolerance,
        )
        try:
            result = connector.collect(request)
        except Exception as exc:  # noqa: BLE001 - logged with its traceback by _fail
            # Connector boundary (C-14, architecture §04.4): one failing source never stops the
            # cycle; the failure is persisted and visible in system/status.
            return self._fail(session, connector, started_at, "CONNECTOR_ERROR", exc)
        context = self._validation_context(session, platform_now)
        try:
            batch = validate(result, context)
        except Exception as exc:  # noqa: BLE001 - logged with its traceback by _fail
            # Output breaking the connector contract (wrong types) fails that connector only.
            return self._fail(session, connector, started_at, "INVALID_CONNECTOR_OUTPUT", exc)
        try:
            with session.begin_nested():
                return self._persist(session, connector, started_at, result, batch)
        except SQLAlchemyError as exc:
            return self._fail(session, connector, started_at, "PERSISTENCE_ERROR", exc)

    def _persist(
        self,
        session: Session,
        connector: Connector,
        started_at: datetime,
        result: CollectionResult,
        batch: ValidatedBatch,
    ) -> CollectionRun:
        runs = CollectionRunRepository(session)
        run_id = runs.open(connector.key, connector.source, started_at)
        received_at = batch.received_at
        observations = ObservationRepository(session)
        samples = observations.insert_samples(batch.samples, connector.source, run_id, received_at)
        logs = observations.insert_logs(batch.logs, connector.source, run_id, received_at)
        issue = result.issues[0] if result.issues else None
        outcome = CollectionOutcome(
            sample_count=samples,
            log_count=logs,
            duplicate_count=len(batch.samples) - samples + len(batch.logs) - logs,
            rejections=batch.rejection_counts(),
            watermark=result.watermark,
            error_code=None if issue is None else issue.code,
            error_message="; ".join(i.message for i in result.issues) or None,
        )
        run = runs.record(run_id, outcome, self._wall.now())
        if result.watermark is not None:
            CollectionCursorRepository(session).save(
                connector.key, connector.source, result.watermark, run.finished_at
            )
        self._log_run(run, batch)
        return run

    def _fail(
        self,
        session: Session,
        connector: Connector,
        started_at: datetime,
        code: str,
        exc: Exception,
    ) -> CollectionRun:
        """Records a failed run; the exception text stays in the logs, never in the API (X-06)."""
        log.exception("collection.failed", connector=connector.key, error_code=code)
        runs = CollectionRunRepository(session)
        run_id = runs.open(connector.key, connector.source, started_at)
        outcome = CollectionOutcome.failed(code, f"{type(exc).__name__}; see worker logs.")
        return runs.record(run_id, outcome, self._wall.now())

    def _validation_context(self, session: Session, now: datetime) -> ValidationContext:
        if self._catalog is None:
            self._catalog = {d.metric_name: d for d in MetricCatalogRepository(session).all()}
        return ValidationContext(now, self._components.ids_by_key(), self._catalog, self._policy)

    @staticmethod
    def _log_run(run: CollectionRun, batch: ValidatedBatch) -> None:
        if run.rejected_count:
            log.warning(
                "collection.rejected",
                connector=run.connector_key,
                collection_run_id=run.id,
                rejections=dict(run.rejections),
                examples=[
                    {"code": r.code, "component": r.component_key, "subject": r.subject}
                    for r in batch.rejections[:MAX_REJECTION_EXAMPLES]
                ],
            )
        log.debug(
            "collection.completed",
            connector=run.connector_key,
            collection_run_id=run.id,
            status=run.status,
            samples=run.sample_count,
            logs=run.log_count,
            duplicates=run.duplicate_count,
        )


def purge_observations(session: Session, cutoff: datetime, batch: int, holds: EvidenceHolds) -> int:
    """Retention of observations, `batch` samples and `batch` logs at most (ADR 0008); held
    evidence stays."""
    return ObservationRepository(session).purge_before(cutoff, batch, holds)


class ObservationReader:
    """Observation reads in the caller's unit of work, for other modules' use cases."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = ObservationRepository(session)

    def collected_until(self) -> datetime | None:
        """Event time up to which every connector has been read (ADR 0015 watermarks): later
        sample slots may still be incomplete. None before any connector has collected."""
        return CollectionCursorRepository(self._session).oldest()

    def units(self) -> dict[str, str]:
        """Canonical unit of every catalogued metric."""
        return {d.metric_name: d.unit for d in MetricCatalogRepository(self._session).all()}

    def samples(
        self,
        component_ids: Sequence[uuid.UUID],
        lookback: Mapping[str, datetime],
        until: datetime,
    ) -> list[StoredSample]:
        """Samples observed in (lookback[metric], until], for each metric of `lookback`."""
        return [
            sample
            for metric_name, after in lookback.items()
            for sample in self._repository.window_samples(component_ids, metric_name, after, until)
        ]

    def marks(
        self, component_ids: Sequence[uuid.UUID], after: datetime, until: datetime
    ) -> list[ObservationMark]:
        return self._repository.marks(component_ids, after, until)

    def samples_by_ids(self, ids: Sequence[int]) -> dict[int, SampleDetail]:
        return {s.id: s for s in self._repository.samples_by_ids(ids)} if ids else {}

    def logs_by_ids(self, ids: Sequence[int]) -> dict[int, StoredLog]:
        return {log.id: log for log in self._repository.logs_by_ids(ids)} if ids else {}


class ObservationHistory:
    """Observation writes in the caller's unit of work, for other modules' use cases."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = ObservationRepository(session)

    def purge_source(self, source: ObservationSource, holds: EvidenceHolds) -> int:
        """Deletes the source's observations, except held evidence, and its collection cursors:
        connectors restart from the source's current coverage instead of resuming after purged
        data."""
        CollectionCursorRepository(self._session).clear(source)
        return self._repository.purge_source(source, holds)


class ObservationQueryService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        topology: TopologyService,
        platform_key: str,
    ) -> None:
        self._session_factory = session_factory
        self._components = _PlatformComponents(topology, platform_key)

    def component_key(self, component_id: uuid.UUID) -> str:
        return self._components.key_of(component_id)

    def series(self, query: SeriesQuery, now: datetime) -> Series:
        """Raw samples when they fit in max_points, otherwise min/avg/max buckets; never filled."""
        component_key = self._components.key_of(query.component_id)
        with self._session_factory() as session:
            definition = MetricCatalogRepository(session).get(query.metric_name)
            if definition is None:
                raise MetricNotFoundError(f"No metric {query.metric_name!r} in the catalog.")
            observations = ObservationRepository(session)
            # One row beyond max_points tells the window needs downsampling, without a count.
            raw = tuple(observations.raw_points(query, query.max_points + 1))
            if len(raw) <= query.max_points:
                gaps = find_gaps([p.observed_at for p in raw], query.window, SAMPLE_INTERVAL_S, now)
                return Series(query, component_key, definition.unit, None, raw, (), gaps)
            bucket_s = query.bucket_seconds()
            buckets = tuple(observations.bucket_points(query, bucket_s))
        times = sorted({b.bucket_start for b in buckets})
        gaps = find_gaps(times, query.window, max(bucket_s, SAMPLE_INTERVAL_S), now)
        return Series(query, component_key, definition.unit, bucket_s, (), buckets, gaps)

    def logs(self, query: LogQuery) -> list[StoredLog]:
        if query.component_id is not None:
            self._components.key_of(query.component_id)
        with self._session_factory() as session:
            return ObservationRepository(session).logs_page(query)

    def recent_runs(self, limit: int) -> list[CollectionRun]:
        with self._session_factory() as session:
            return CollectionRunRepository(session).recent(limit)

    def latest_runs(self, connector_key: str) -> tuple[CollectionRun | None, CollectionRun | None]:
        """Latest run of the connector, and its latest successful (`ok`) run."""
        with self._session_factory() as session:
            runs = CollectionRunRepository(session)
            return runs.latest(connector_key, None), runs.latest(connector_key, CollectionStatus.OK)
