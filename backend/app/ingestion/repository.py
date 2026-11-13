import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, cast

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Delete,
    Double,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    case,
    delete,
    func,
    literal,
    select,
    tuple_,
)
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.types import TIMESTAMP, Interval, TypeEngine, Uuid

from app.core.db import Base, check_in
from app.core.observation import LogSeverity, ObservationSource, Quality
from app.ingestion.domain.catalog import MetricDefinition, MetricKind
from app.ingestion.domain.collection import (
    MAX_ERROR_MESSAGE_CHARS,
    CollectionOutcome,
    CollectionRun,
    CollectionStatus,
)
from app.ingestion.domain.logs import LogQuery, StoredLog
from app.ingestion.domain.observations import ObservationMark, StoredSample
from app.ingestion.domain.series import (
    BucketPoint,
    RawPoint,
    SeriesQuery,
    TimeWindow,
)
from app.ingestion.domain.validation import AcceptedLog, AcceptedSample

SAMPLE_UNIQUE = "uq_metric_sample_component_id_metric_name_observed_at_source"
LOG_UNIQUE = "uq_log_event_component_id_observed_at_source_dedup_key"


class MetricDefinitionRecord(Base):
    __tablename__ = "metric_definition"
    __table_args__ = (
        CheckConstraint(check_in("kind", MetricKind), name="kind"),
        CheckConstraint("min_value < max_value", name="range"),
    )

    metric_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    unit: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(String(256))
    min_value: Mapped[float] = mapped_column(Double)
    max_value: Mapped[float] = mapped_column(Double)
    kind: Mapped[str] = mapped_column(String(16))


class CollectionRunRecord(Base):
    __tablename__ = "collection_run"
    __table_args__ = (
        CheckConstraint(check_in("status", CollectionStatus), name="status"),
        CheckConstraint(check_in("source", ObservationSource), name="source"),
        CheckConstraint(
            "sample_count >= 0 AND log_count >= 0 AND rejected_count >= 0 AND duplicate_count >= 0",
            name="counts_non_negative",
        ),
        CheckConstraint("finished_at >= started_at", name="finishes_after_start"),
        Index("ix_collection_run_connector_key_started_at", "connector_key", "started_at"),
        Index("ix_collection_run_started_at", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    connector_key: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(16))
    sample_count: Mapped[int] = mapped_column(Integer)
    log_count: Mapped[int] = mapped_column(Integer)
    rejected_count: Mapped[int] = mapped_column(Integer)
    duplicate_count: Mapped[int] = mapped_column(Integer)
    rejections: Mapped[dict[str, int]] = mapped_column(JSONB)
    watermark: Mapped[datetime | None]
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(MAX_ERROR_MESSAGE_CHARS))


class CollectionCursorRecord(Base):
    """Where each connector resumes; state, unlike the collection_run history."""

    __tablename__ = "collection_cursor"
    __table_args__ = (CheckConstraint(check_in("source", ObservationSource), name="source"),)

    connector_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    source: Mapped[str] = mapped_column(String(16))
    watermark: Mapped[datetime]
    updated_at: Mapped[datetime]


class MetricSampleRecord(Base):
    __tablename__ = "metric_sample"
    __table_args__ = (
        # Re-delivered samples are ignored and counted (ADR 0003). The unique index also serves
        # series reads (component, metric, time range), so no second composite index is kept.
        UniqueConstraint("component_id", "metric_name", "observed_at", "source"),
        CheckConstraint(check_in("quality", Quality), name="quality"),
        CheckConstraint(check_in("source", ObservationSource), name="source"),
        CheckConstraint("value = value", name="value_not_nan"),
        Index("ix_metric_sample_observed_at_brin", "observed_at", postgresql_using="brin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    component_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("component.id"))
    metric_name: Mapped[str] = mapped_column(ForeignKey("metric_definition.metric_name"))
    value: Mapped[float] = mapped_column(Double)
    unit: Mapped[str] = mapped_column(String(16))
    quality: Mapped[str] = mapped_column(String(16))
    observed_at: Mapped[datetime]
    received_at: Mapped[datetime]
    source: Mapped[str] = mapped_column(String(16))
    scenario_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenario_run.id"))
    collection_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collection_run.id"))


class LogEventRecord(Base):
    __tablename__ = "log_event"
    __table_args__ = (
        # Leading (component_id, observed_at) also serves per-component log reads.
        UniqueConstraint("component_id", "observed_at", "source", "dedup_key"),
        CheckConstraint(check_in("severity", LogSeverity), name="severity"),
        CheckConstraint(check_in("source", ObservationSource), name="source"),
        CheckConstraint("char_length(message) BETWEEN 1 AND 2000", name="message_length"),
        Index("ix_log_event_fingerprint_observed_at", "fingerprint", "observed_at"),
        # Serves unfiltered newest-first pages (keyset on observed_at, id) and retention.
        Index("ix_log_event_observed_at_id", "observed_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    component_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("component.id"))
    severity: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(String(2000))
    fingerprint: Mapped[str] = mapped_column(String(16))
    dedup_key: Mapped[str] = mapped_column(String(32))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    observed_at: Mapped[datetime]
    received_at: Mapped[datetime]
    source: Mapped[str] = mapped_column(String(16))
    scenario_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenario_run.id"))
    collection_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collection_run.id"))


class MetricCatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, definitions: Iterable[MetricDefinition]) -> None:
        for d in definitions:
            values = {
                "unit": d.unit,
                "description": d.description,
                "min_value": d.min_value,
                "max_value": d.max_value,
                "kind": d.kind.value,
            }
            statement = insert(MetricDefinitionRecord).values(metric_name=d.metric_name, **values)
            self._session.execute(
                statement.on_conflict_do_update(index_elements=["metric_name"], set_=values)
            )

    def all(self) -> list[MetricDefinition]:
        statement = select(MetricDefinitionRecord).order_by(MetricDefinitionRecord.metric_name)
        return [_to_definition(r) for r in self._session.scalars(statement)]

    def get(self, metric_name: str) -> MetricDefinition | None:
        record = self._session.get(MetricDefinitionRecord, metric_name)
        return None if record is None else _to_definition(record)


def _to_definition(r: MetricDefinitionRecord) -> MetricDefinition:
    return MetricDefinition(
        r.metric_name, r.unit, r.description, r.min_value, r.max_value, MetricKind(r.kind)
    )


class CollectionRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def open(
        self, connector_key: str, source: ObservationSource, started_at: datetime
    ) -> uuid.UUID:
        """Inserted first so observations can reference it; `record` fills in the outcome."""
        record = CollectionRunRecord(
            connector_key=connector_key,
            source=source.value,
            started_at=started_at,
            finished_at=started_at,
            status=CollectionStatus.FAILED.value,
            sample_count=0,
            log_count=0,
            rejected_count=0,
            duplicate_count=0,
            rejections={},
        )
        self._session.add(record)
        self._session.flush()
        return record.id

    def record(
        self, run_id: uuid.UUID, outcome: CollectionOutcome, finished_at: datetime
    ) -> CollectionRun:
        record = self._session.get_one(CollectionRunRecord, run_id)
        record.finished_at = finished_at
        record.status = outcome.status.value
        record.sample_count = outcome.sample_count
        record.log_count = outcome.log_count
        record.rejected_count = outcome.rejected_count
        record.duplicate_count = outcome.duplicate_count
        record.rejections = dict(outcome.rejections or {})
        record.watermark = outcome.watermark
        record.error_code = outcome.error_code
        # Bounded by the column; connectors may report arbitrarily long messages.
        record.error_message = (outcome.error_message or "")[:MAX_ERROR_MESSAGE_CHARS] or None
        self._session.flush()
        return _to_run(record)

    def recent(self, limit: int) -> list[CollectionRun]:
        statement = (
            select(CollectionRunRecord)
            .order_by(CollectionRunRecord.started_at.desc(), CollectionRunRecord.id.desc())
            .limit(limit)
        )
        return [_to_run(r) for r in self._session.scalars(statement)]

    def latest(self, connector_key: str, status: CollectionStatus | None) -> CollectionRun | None:
        statement = select(CollectionRunRecord).where(
            CollectionRunRecord.connector_key == connector_key
        )
        if status is not None:
            statement = statement.where(CollectionRunRecord.status == status.value)
        statement = statement.order_by(CollectionRunRecord.started_at.desc()).limit(1)
        record = self._session.scalars(statement).first()
        return None if record is None else _to_run(record)


class CollectionCursorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, connector_key: str) -> datetime | None:
        record = self._session.get(CollectionCursorRecord, connector_key)
        return None if record is None else record.watermark

    def save(
        self,
        connector_key: str,
        source: ObservationSource,
        watermark: datetime,
        updated_at: datetime,
    ) -> None:
        values = {"source": source.value, "watermark": watermark, "updated_at": updated_at}
        statement = insert(CollectionCursorRecord).values(connector_key=connector_key, **values)
        self._session.execute(
            statement.on_conflict_do_update(index_elements=["connector_key"], set_=values)
        )

    def clear(self, source: ObservationSource) -> None:
        self._session.execute(
            delete(CollectionCursorRecord).where(CollectionCursorRecord.source == source.value)
        )

    def oldest(self) -> datetime | None:
        """Lowest watermark across connectors; None before any connector has collected."""
        return self._session.execute(select(func.min(CollectionCursorRecord.watermark))).scalar()


def _to_run(record: CollectionRunRecord) -> CollectionRun:
    return CollectionRun(
        id=record.id,
        connector_key=record.connector_key,
        source=ObservationSource(record.source),
        started_at=record.started_at,
        finished_at=record.finished_at,
        status=CollectionStatus(record.status),
        sample_count=record.sample_count,
        log_count=record.log_count,
        rejected_count=record.rejected_count,
        duplicate_count=record.duplicate_count,
        rejections=MappingProxyType(dict(record.rejections)),
        watermark=record.watermark,
        error_code=record.error_code,
        error_message=record.error_message,
    )


class ObservationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert_samples(
        self,
        samples: Sequence[AcceptedSample],
        source: ObservationSource,
        run_id: uuid.UUID,
        received_at: datetime,
    ) -> int:
        """Inserted count; samples already stored under the same key are skipped."""
        columns: _Columns = {
            "component_id": (Uuid(), [s.component_id for s in samples]),
            "metric_name": (String(), [s.metric_name for s in samples]),
            "value": (Double(), [s.value for s in samples]),
            "unit": (String(), [s.unit for s in samples]),
            "quality": (String(), [s.quality.value for s in samples]),
            "observed_at": (_TIMESTAMPTZ, [s.observed_at for s in samples]),
            "scenario_run_id": (Uuid(), [s.scenario_run_id for s in samples]),
        }
        constants = _batch_constants(source, run_id, received_at)
        return self._insert_new(MetricSampleRecord, SAMPLE_UNIQUE, columns, constants)

    def insert_logs(
        self,
        logs: Sequence[AcceptedLog],
        source: ObservationSource,
        run_id: uuid.UUID,
        received_at: datetime,
    ) -> int:
        columns: _Columns = {
            "component_id": (Uuid(), [e.component_id for e in logs]),
            "severity": (String(), [e.severity.value for e in logs]),
            "message": (String(), [e.message for e in logs]),
            "fingerprint": (String(), [e.fingerprint for e in logs]),
            "dedup_key": (String(), [e.dedup_key for e in logs]),
            "attributes": (JSONB(), [dict(e.attributes) for e in logs]),
            "observed_at": (_TIMESTAMPTZ, [e.observed_at for e in logs]),
            "scenario_run_id": (Uuid(), [e.scenario_run_id for e in logs]),
        }
        constants = _batch_constants(source, run_id, received_at)
        return self._insert_new(LogEventRecord, LOG_UNIQUE, columns, constants)

    def _insert_new(
        self,
        record: type[MetricSampleRecord] | type[LogEventRecord],
        constraint: str,
        columns: _Columns,
        constants: dict[str, Any],
    ) -> int:
        """INSERT … SELECT FROM unnest(arrays): one parameter per column, not per value.

        A multi-row VALUES list costs the driver a parse of thousands of placeholders per
        batch; arrays keep the statement small whatever the catch-up volume.
        """
        size = len(next(iter(columns.values()))[1])
        if size == 0:
            return 0
        arrays = [sql_cast(literal(v, ARRAY(t)), ARRAY(t)) for t, v in columns.values()]
        rows = func.unnest(*arrays).table_valued(*columns).render_derived()
        selected = [*rows.c, *(literal(v).label(k) for k, v in constants.items())]
        statement = (
            insert(record)
            .from_select([*columns, *constants], select(*selected))
            .on_conflict_do_nothing(constraint=constraint)
            .returning(record.id)
        )
        # RETURNING lists only the rows actually inserted; through the ORM session, rowcount
        # is not reported (-1) for this statement.
        return len(self._session.scalars(statement).all())

    def raw_points(self, query: SeriesQuery, limit: int) -> list[RawPoint]:
        statement = (
            select(
                MetricSampleRecord.id,
                MetricSampleRecord.observed_at,
                MetricSampleRecord.value,
                MetricSampleRecord.quality,
                MetricSampleRecord.source,
                MetricSampleRecord.scenario_run_id,
            )
            .where(*_series_filter(query.component_id, query.metric_name, query.window))
            .order_by(MetricSampleRecord.observed_at, MetricSampleRecord.source)
            .limit(limit)
        )
        return [
            RawPoint(
                r.id,
                r.observed_at,
                r.value,
                Quality(r.quality),
                ObservationSource(r.source),
                r.scenario_run_id,
            )
            for r in self._session.execute(statement)
        ]

    def bucket_points(self, query: SeriesQuery, bucket_s: int) -> list[BucketPoint]:
        bucket = func.date_bin(
            literal(timedelta(seconds=bucket_s), Interval),
            MetricSampleRecord.observed_at,
            literal(query.window.start, TIMESTAMP(timezone=True)),
        ).label("bucket")
        # Quality is declared best to worst: buckets keep their worst quality (D-16).
        qualities = tuple(Quality)
        rank = case(*((MetricSampleRecord.quality == q.value, i) for i, q in enumerate(qualities)))
        statement = (
            select(
                bucket,
                MetricSampleRecord.source,
                func.min(MetricSampleRecord.value),
                func.avg(MetricSampleRecord.value),
                func.max(MetricSampleRecord.value),
                func.count(),
                func.max(rank),
            )
            .where(*_series_filter(query.component_id, query.metric_name, query.window))
            .group_by(bucket, MetricSampleRecord.source)
            .order_by(bucket, MetricSampleRecord.source)
            .limit(query.max_points * len(ObservationSource))
        )
        return [
            BucketPoint(
                bucket_start=row[0],
                minimum=row[2],
                average=float(row[3]),
                maximum=row[4],
                count=row[5],
                worst_quality=qualities[row[6]],
                source=ObservationSource(row[1]),
            )
            for row in self._session.execute(statement)
        ]

    def logs_page(self, query: LogQuery) -> list[StoredLog]:
        """Newest first; keyset on (observed_at, id) so pages stay stable while logs arrive."""
        statement = select(LogEventRecord).where(
            LogEventRecord.observed_at >= query.window.start,
            LogEventRecord.observed_at < query.window.end,
        )
        if query.component_id is not None:
            statement = statement.where(LogEventRecord.component_id == query.component_id)
        if query.min_severity is not None:
            kept = [s.value for s in LogSeverity if s.rank >= query.min_severity.rank]
            statement = statement.where(LogEventRecord.severity.in_(kept))
        if query.before is not None:
            statement = statement.where(
                tuple_(LogEventRecord.observed_at, LogEventRecord.id)
                < tuple_(literal(query.before.observed_at), literal(query.before.id))
            )
        statement = statement.order_by(
            LogEventRecord.observed_at.desc(), LogEventRecord.id.desc()
        ).limit(query.limit)
        return [
            StoredLog(
                id=r.id,
                component_id=r.component_id,
                severity=LogSeverity(r.severity),
                message=r.message,
                fingerprint=r.fingerprint,
                attributes=MappingProxyType(dict(r.attributes)),
                observed_at=r.observed_at,
                received_at=r.received_at,
                source=ObservationSource(r.source),
                scenario_run_id=r.scenario_run_id,
            )
            for r in self._session.scalars(statement)
        ]

    def window_samples(
        self,
        component_ids: Sequence[uuid.UUID],
        metric_name: str,
        after: datetime,
        until: datetime,
    ) -> list[StoredSample]:
        """Samples of one metric in (after, until]; served by the unique index per component."""
        statement = select(
            MetricSampleRecord.id,
            MetricSampleRecord.component_id,
            MetricSampleRecord.value,
            MetricSampleRecord.quality,
            MetricSampleRecord.observed_at,
        ).where(
            MetricSampleRecord.component_id.in_(component_ids),
            MetricSampleRecord.metric_name == metric_name,
            MetricSampleRecord.observed_at > after,
            MetricSampleRecord.observed_at <= until,
        )
        return [
            StoredSample(
                r.id, r.component_id, metric_name, r.value, Quality(r.quality), r.observed_at
            )
            for r in self._session.execute(statement)
        ]

    def marks(
        self, component_ids: Sequence[uuid.UUID], after: datetime, until: datetime
    ) -> list[ObservationMark]:
        """One mark per component and instant observed in (after, until], samples first."""
        marks: dict[tuple[uuid.UUID, datetime], ObservationMark] = {}
        for record, is_sample in ((MetricSampleRecord, True), (LogEventRecord, False)):
            statement = (
                select(record.component_id, record.observed_at, func.min(record.id))
                .where(
                    record.component_id.in_(component_ids),
                    record.observed_at > after,
                    record.observed_at <= until,
                )
                .group_by(record.component_id, record.observed_at)
            )
            for component_id, observed_at, first_id in self._session.execute(statement):
                marks.setdefault(
                    (component_id, observed_at),
                    ObservationMark(
                        component_id,
                        observed_at,
                        first_id if is_sample else None,
                        None if is_sample else first_id,
                    ),
                )
        return list(marks.values())

    def purge_before(self, cutoff: datetime, batch: int) -> int:
        """Deletes at most `batch` samples and `batch` logs observed before `cutoff`."""
        deleted = 0
        for record in (MetricSampleRecord, LogEventRecord):
            oldest = select(record.id).where(record.observed_at < cutoff).limit(batch)
            deleted += self._deleted(delete(record).where(record.id.in_(oldest.scalar_subquery())))
        return deleted

    def _deleted(self, statement: Delete) -> int:
        return cast(CursorResult[Any], self._session.execute(statement)).rowcount

    def purge_source(self, source: ObservationSource) -> int:
        deleted = 0
        for record in (MetricSampleRecord, LogEventRecord):
            deleted += self._deleted(delete(record).where(record.source == source.value))
        return deleted


def _series_filter(
    component_id: uuid.UUID, metric_name: str, window: TimeWindow
) -> tuple[Any, ...]:
    return (
        MetricSampleRecord.component_id == component_id,
        MetricSampleRecord.metric_name == metric_name,
        MetricSampleRecord.observed_at >= window.start,
        MetricSampleRecord.observed_at < window.end,
    )


_TIMESTAMPTZ = TIMESTAMP(timezone=True)
# Column name -> (SQL type, one value per row), for INSERT ... SELECT FROM unnest.
type _Columns = dict[str, tuple[TypeEngine[Any], list[Any]]]


def _batch_constants(
    source: ObservationSource, run_id: uuid.UUID, received_at: datetime
) -> dict[str, Any]:
    return {"received_at": received_at, "source": source.value, "collection_run_id": run_id}
