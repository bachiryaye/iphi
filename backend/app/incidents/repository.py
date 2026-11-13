import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ColumnElement,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Select,
    String,
    UniqueConstraint,
    exists,
    func,
    literal,
    or_,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, distinct_on, insert
from sqlalchemy.orm import InstrumentedAttribute, Mapped, Session, mapped_column
from sqlalchemy.sql.selectable import Subquery

from app.core.db import Base, check_in
from app.core.observation import ObservationSource
from app.core.retention import EvidenceHolds, RowHold
from app.health.domain.rules import FailureClass
from app.incidents.domain.model import (
    Actor,
    ActorType,
    EventType,
    EvidenceLink,
    EvidenceRole,
    Fingerprint,
    Impact,
    Incident,
    IncidentEvent,
    IncidentSeverity,
    IncidentStatus,
    Resolution,
    StoredEvent,
)
from app.incidents.domain.records import (
    EventPosition,
    ImpactView,
    IncidentFilter,
    StoredEvidence,
)

_ACTIVE = "status <> 'resolved'"


class IncidentRecord(Base):
    __tablename__ = "incident"
    __table_args__ = (
        CheckConstraint(check_in("failure_class", FailureClass), name="failure_class"),
        CheckConstraint(check_in("status", IncidentStatus), name="status"),
        CheckConstraint(check_in("severity", IncidentSeverity), name="severity"),
        CheckConstraint(check_in("peak_severity", IncidentSeverity), name="peak_severity"),
        CheckConstraint(
            f"resolution IS NULL OR {check_in('resolution', Resolution)}", name="resolution"
        ),
        CheckConstraint(check_in("source", ObservationSource), name="source"),
        CheckConstraint(
            "(status = 'resolved') = (resolved_at IS NOT NULL) "
            "AND (resolved_at IS NULL) = (resolved_by IS NULL) "
            "AND (resolved_at IS NULL) = (resolution IS NULL)",
            name="resolution_complete",
        ),
        CheckConstraint(
            "(acknowledged_at IS NULL) = (acknowledged_by IS NULL) "
            "AND (status <> 'acknowledged' OR acknowledged_at IS NOT NULL)",
            name="acknowledgement_complete",
        ),
        CheckConstraint(
            "occurrence_count >= 1 AND reopen_count >= 0 AND last_seen_at >= opened_at",
            name="counts_consistent",
        ),
        # D-10: at most one active incident per fingerprint, enforced by the database.
        Index(
            "uq_incident_fingerprint_active",
            "fingerprint",
            unique=True,
            postgresql_where=text(_ACTIVE),
        ),
        Index("ix_incident_status_opened_at", "status", text("opened_at DESC")),
        Index("ix_incident_component_id_opened_at", "component_id", text("opened_at DESC")),
        Index("ix_incident_opened_at_number", "opened_at", "number"),
        Index("ix_incident_fingerprint_resolved_at", "fingerprint", "resolved_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    platform_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.id"))
    component_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("component.id"))
    failure_class: Mapped[str] = mapped_column(String(32))
    fingerprint: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(16))
    peak_severity: Mapped[str] = mapped_column(String(16))
    opened_at: Mapped[datetime]
    last_seen_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    acknowledged_at: Mapped[datetime | None]
    acknowledged_by: Mapped[str | None] = mapped_column(String(64))
    resolved_at: Mapped[datetime | None]
    resolved_by: Mapped[str | None] = mapped_column(String(64))
    resolution: Mapped[str | None] = mapped_column(String(16))
    occurrence_count: Mapped[int] = mapped_column(Integer)
    reopen_count: Mapped[int] = mapped_column(Integer)
    scenario_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenario_run.id"))
    source: Mapped[str] = mapped_column(String(16))


class IncidentEvidenceRecord(Base):
    """Append-only (D-12): a trigger of migration 0005 rejects UPDATE and DELETE."""

    __tablename__ = "incident_evidence"
    __table_args__ = (
        CheckConstraint(check_in("role", EvidenceRole), name="role"),
        CheckConstraint(
            "num_nonnulls(metric_sample_id, log_event_id, rule_evaluation_id) = 1",
            name="one_reference",
        ),
        UniqueConstraint(
            "incident_id",
            "metric_sample_id",
            "log_event_id",
            "rule_evaluation_id",
            name="uq_incident_evidence_reference",
            postgresql_nulls_not_distinct=True,
        ),
        # Retention and reset check every candidate row against these (foreign keys and holds).
        Index(
            "ix_incident_evidence_metric_sample_id",
            "metric_sample_id",
            postgresql_where=text("metric_sample_id IS NOT NULL"),
        ),
        Index(
            "ix_incident_evidence_log_event_id",
            "log_event_id",
            postgresql_where=text("log_event_id IS NOT NULL"),
        ),
        Index(
            "ix_incident_evidence_rule_evaluation_id",
            "rule_evaluation_id",
            postgresql_where=text("rule_evaluation_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incident.id"))
    metric_sample_id: Mapped[int | None] = mapped_column(ForeignKey("metric_sample.id"))
    log_event_id: Mapped[int | None] = mapped_column(ForeignKey("log_event.id"))
    rule_evaluation_id: Mapped[int | None] = mapped_column(ForeignKey("rule_evaluation.id"))
    role: Mapped[str] = mapped_column(String(16))
    added_at: Mapped[datetime]


class IncidentEventRecord(Base):
    """Append-only (D-12): a trigger of migration 0005 rejects UPDATE and DELETE."""

    __tablename__ = "incident_event"
    __table_args__ = (
        CheckConstraint(check_in("event_type", EventType), name="event_type"),
        CheckConstraint(check_in("actor_type", ActorType), name="actor_type"),
        Index("ix_incident_event_incident_id_occurred_at", "incident_id", "occurred_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incident.id"))
    event_type: Mapped[str] = mapped_column(String(32))
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[uuid.UUID | None]
    actor_label: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class IncidentImpactRecord(Base):
    """Append-only: a trigger of migration 0005 rejects UPDATE and DELETE."""

    __tablename__ = "incident_impact"

    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incident.id"), primary_key=True)
    component_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("component.id"), primary_key=True)
    since: Mapped[datetime]


_MUTABLE = (
    "failure_class",
    "fingerprint",
    "title",
    "status",
    "severity",
    "peak_severity",
    "last_seen_at",
    "updated_at",
    "acknowledged_at",
    "acknowledged_by",
    "resolved_at",
    "resolved_by",
    "resolution",
    "occurrence_count",
    "reopen_count",
)


class IncidentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def active(self, platform_id: uuid.UUID | None, *, for_update: bool) -> list[Incident]:
        """Active incidents of a platform, or of all; locked in ID order, so concurrent lockers
        never deadlock on these rows."""
        statement = select(IncidentRecord).where(text(_ACTIVE)).order_by(IncidentRecord.id)
        if platform_id is not None:
            statement = statement.where(IncidentRecord.platform_id == platform_id)
        if for_update:
            statement = statement.with_for_update()
        return [_to_incident(r) for r in self._session.scalars(statement)]

    def latest_resolved(self, platform_id: uuid.UUID, since: datetime) -> list[Incident]:
        """The latest incident of each fingerprint resolved at `since` or later, locked: the
        worker may reopen it while a diagnosis is being added."""
        latest = (
            select(IncidentRecord.id)
            .where(
                IncidentRecord.platform_id == platform_id,
                IncidentRecord.status == IncidentStatus.RESOLVED.value,
                IncidentRecord.resolved_at >= since,
            )
            .order_by(IncidentRecord.fingerprint, IncidentRecord.resolved_at.desc())
            .ext(distinct_on(IncidentRecord.fingerprint))
        )
        statement = (
            select(IncidentRecord)
            .where(IncidentRecord.id.in_(latest.scalar_subquery()))
            .order_by(IncidentRecord.id)
            .with_for_update()
        )
        return [_to_incident(r) for r in self._session.scalars(statement)]

    def get(self, incident_id: uuid.UUID, *, for_update: bool) -> Incident | None:
        statement = select(IncidentRecord).where(IncidentRecord.id == incident_id)
        if for_update:
            statement = statement.with_for_update()
        record = self._session.scalars(statement).one_or_none()
        return None if record is None else _to_incident(record)

    def insert(self, incidents: Sequence[Incident]) -> dict[uuid.UUID, int]:
        """Numbers assigned by the database, by incident ID. A second active incident with the
        same fingerprint violates the partial unique index and raises IntegrityError."""
        if not incidents:
            return {}
        rows = [{"id": i.id, **_columns(i)} for i in incidents]
        statement = insert(IncidentRecord).returning(IncidentRecord.id, IncidentRecord.number)
        return {r.id: r.number for r in self._session.execute(statement, rows)}

    def update(self, incidents: Iterable[Incident]) -> None:
        for incident in incidents:
            values = {k: v for k, v in _columns(incident).items() if k in _MUTABLE}
            self._session.execute(
                update(IncidentRecord).where(IncidentRecord.id == incident.id).values(values)
            )

    def add_events(self, events: Sequence[IncidentEvent]) -> None:
        if not events:
            return
        rows = [
            {
                "incident_id": e.incident_id,
                "event_type": e.type.value,
                "actor_type": e.actor.type.value,
                "actor_id": e.actor.id,
                "actor_label": e.actor.label,
                "occurred_at": e.occurred_at,
                "payload": dict(e.payload),
            }
            for e in events
        ]
        self._session.execute(insert(IncidentEventRecord), rows)

    def add_evidence(self, links: Sequence[EvidenceLink]) -> None:
        """Rows already linked to the incident keep their first role."""
        if not links:
            return
        rows = [
            {
                "incident_id": link.incident_id,
                "metric_sample_id": link.ref.sample_id,
                "log_event_id": link.ref.log_id,
                "rule_evaluation_id": link.ref.evaluation_id,
                "role": link.role.value,
                "added_at": link.added_at,
            }
            for link in links
        ]
        self._session.execute(insert(IncidentEvidenceRecord).on_conflict_do_nothing(), rows)

    def add_impacts(self, impacts: Sequence[Impact]) -> None:
        if not impacts:
            return
        rows = [
            {"incident_id": i.incident_id, "component_id": i.component_id, "since": i.since}
            for i in impacts
        ]
        self._session.execute(insert(IncidentImpactRecord).on_conflict_do_nothing(), rows)

    def impacts(self, incident_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[ImpactView]]:
        found: dict[uuid.UUID, list[ImpactView]] = defaultdict(list)
        if not incident_ids:
            return found
        statement = (
            select(IncidentImpactRecord)
            .where(IncidentImpactRecord.incident_id.in_(incident_ids))
            .order_by(IncidentImpactRecord.since, IncidentImpactRecord.component_id)
        )
        for r in self._session.scalars(statement):
            found[r.incident_id].append(ImpactView(r.component_id, r.since))
        return found

    def page(self, query: IncidentFilter) -> list[Incident]:
        """Newest opened first; keyset on (opened_at, number)."""
        record = IncidentRecord
        statement = select(record)
        if query.platform_id is not None:
            statement = statement.where(record.platform_id == query.platform_id)
        if query.statuses:
            statement = statement.where(record.status.in_(sorted(s.value for s in query.statuses)))
        if query.severity is not None:
            statement = statement.where(record.severity == query.severity.value)
        if query.component_id is not None:
            statement = statement.where(record.component_id == query.component_id)
        if query.failure_class is not None:
            statement = statement.where(record.failure_class == query.failure_class.value)
        if query.opened_from is not None:
            statement = statement.where(record.opened_at >= query.opened_from)
        if query.opened_to is not None:
            statement = statement.where(record.opened_at < query.opened_to)
        if query.before is not None:
            statement = statement.where(
                tuple_(record.opened_at, record.number)
                < tuple_(literal(query.before.opened_at), literal(query.before.number))
            )
        statement = statement.order_by(record.opened_at.desc(), record.number.desc()).limit(
            query.limit
        )
        return [_to_incident(r) for r in self._session.scalars(statement)]

    def evidence_counts(self, incident_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not incident_ids:
            return {}
        statement = (
            select(IncidentEvidenceRecord.incident_id, func.count().label("total"))
            .where(IncidentEvidenceRecord.incident_id.in_(incident_ids))
            .group_by(IncidentEvidenceRecord.incident_id)
        )
        return {row.incident_id: row.total for row in self._session.execute(statement)}

    def evidence(
        self, incident_id: uuid.UUID, after: int | None, limit: int
    ) -> list[StoredEvidence]:
        """In insertion order, with each row's ordinal within the incident."""
        numbered = _numbered_evidence(incident_id)
        statement = select(numbered).order_by(numbered.c.id).limit(limit)
        if after is not None:
            statement = statement.where(numbered.c.id > after)
        return _evidence_rows(self._session, statement)

    def key_evaluations(self, incident_id: uuid.UUID, limit: int) -> list[StoredEvidence]:
        """Evaluations that opened, impacted or recovered the incident, oldest first."""
        numbered = _numbered_evidence(incident_id)
        key_roles = [r.value for r in EvidenceRole if r is not EvidenceRole.SUPPORTING]
        statement = (
            select(numbered)
            .where(numbered.c.rule_evaluation_id.is_not(None), numbered.c.role.in_(key_roles))
            .order_by(numbered.c.id)
            .limit(limit)
        )
        return _evidence_rows(self._session, statement)

    def latest_supporting_evaluations(
        self, incident_id: uuid.UUID, limit: int
    ) -> list[StoredEvidence]:
        numbered = _numbered_evidence(incident_id)
        statement = (
            select(numbered)
            .where(
                numbered.c.rule_evaluation_id.is_not(None),
                numbered.c.role == EvidenceRole.SUPPORTING.value,
            )
            .order_by(numbered.c.id.desc())
            .limit(limit)
        )
        return _evidence_rows(self._session, statement)

    def observation_evidence(
        self, incident_id: uuid.UUID, sample_ids: Sequence[int], log_ids: Sequence[int]
    ) -> list[StoredEvidence]:
        """Evidence rows of these observations, oldest first."""
        numbered = _numbered_evidence(incident_id)
        statement = (
            select(numbered)
            .where(
                or_(
                    numbered.c.metric_sample_id.in_(sample_ids),
                    numbered.c.log_event_id.in_(log_ids),
                )
            )
            .order_by(numbered.c.id)
            .limit(len(sample_ids) + len(log_ids))
        )
        return _evidence_rows(self._session, statement)

    def has_log_evidence(self, incident_id: uuid.UUID) -> bool:
        statement = select(
            exists().where(
                IncidentEvidenceRecord.incident_id == incident_id,
                IncidentEvidenceRecord.log_event_id.is_not(None),
            )
        )
        return bool(self._session.execute(statement).scalar_one())

    def events(
        self, incident_id: uuid.UUID, after: EventPosition | None, limit: int
    ) -> list[StoredEvent]:
        """Oldest first; keyset on (occurred_at, id)."""
        record = IncidentEventRecord
        statement = select(record).where(record.incident_id == incident_id)
        if after is not None:
            statement = statement.where(
                tuple_(record.occurred_at, record.id)
                > tuple_(literal(after.occurred_at), literal(after.id))
            )
        statement = statement.order_by(record.occurred_at, record.id).limit(limit)
        return [_to_event(r) for r in self._session.scalars(statement)]

    def event_count(self, incident_id: uuid.UUID) -> int:
        statement = select(func.count()).where(IncidentEventRecord.incident_id == incident_id)
        return self._session.execute(statement).scalar_one()

    def overlapping(
        self, component_ids: Iterable[uuid.UUID], start: datetime, end: datetime, limit: int
    ) -> list[Incident]:
        """Incidents of these components active at some point of [start, end], oldest first."""
        ids = list(component_ids)
        if not ids:
            return []
        statement = (
            select(IncidentRecord)
            .where(
                IncidentRecord.component_id.in_(ids),
                IncidentRecord.opened_at <= end,
                or_(IncidentRecord.resolved_at.is_(None), IncidentRecord.resolved_at >= start),
            )
            .order_by(IncidentRecord.opened_at, IncidentRecord.number)
            .limit(limit)
        )
        return [_to_incident(r) for r in self._session.scalars(statement)]


def _numbered_evidence(incident_id: uuid.UUID) -> Subquery:
    return (
        select(
            IncidentEvidenceRecord,
            func.row_number().over(order_by=IncidentEvidenceRecord.id).label("ordinal"),
        )
        .where(IncidentEvidenceRecord.incident_id == incident_id)
        .subquery()
    )


def _evidence_rows(session: Session, statement: Select[Any]) -> list[StoredEvidence]:
    return [_to_evidence(row._mapping) for row in session.execute(statement)]


def evidence_holds() -> EvidenceHolds:
    """Observations and evaluations cited as incident evidence, kept by retention and reset."""
    return EvidenceHolds(
        samples=_cited_by(IncidentEvidenceRecord.metric_sample_id),
        logs=_cited_by(IncidentEvidenceRecord.log_event_id),
        evaluations=_cited_by(IncidentEvidenceRecord.rule_evaluation_id),
    )


def _cited_by(reference: InstrumentedAttribute[int | None]) -> RowHold:
    def hold(row_id: ColumnElement[int]) -> ColumnElement[bool]:
        return exists().where(reference == row_id)

    return hold


def _columns(i: Incident) -> dict[str, Any]:
    return {
        "platform_id": i.platform_id,
        "component_id": i.component_id,
        "failure_class": i.failure_class.value,
        "fingerprint": i.fingerprint.value,
        "title": i.title,
        "status": i.status.value,
        "severity": i.severity.value,
        "peak_severity": i.peak_severity.value,
        "opened_at": i.opened_at,
        "last_seen_at": i.last_seen_at,
        "updated_at": i.updated_at,
        "acknowledged_at": i.acknowledged_at,
        "acknowledged_by": i.acknowledged_by,
        "resolved_at": i.resolved_at,
        "resolved_by": i.resolved_by,
        "resolution": None if i.resolution is None else i.resolution.value,
        "occurrence_count": i.occurrence_count,
        "reopen_count": i.reopen_count,
        "scenario_run_id": i.scenario_run_id,
        "source": i.source.value,
    }


def _to_incident(r: IncidentRecord) -> Incident:
    return Incident(
        id=r.id,
        number=r.number,
        platform_id=r.platform_id,
        component_id=r.component_id,
        failure_class=FailureClass(r.failure_class),
        fingerprint=Fingerprint(r.fingerprint),
        title=r.title,
        status=IncidentStatus(r.status),
        severity=IncidentSeverity(r.severity),
        peak_severity=IncidentSeverity(r.peak_severity),
        opened_at=r.opened_at,
        last_seen_at=r.last_seen_at,
        updated_at=r.updated_at,
        acknowledged_at=r.acknowledged_at,
        acknowledged_by=r.acknowledged_by,
        resolved_at=r.resolved_at,
        resolved_by=r.resolved_by,
        resolution=None if r.resolution is None else Resolution(r.resolution),
        occurrence_count=r.occurrence_count,
        reopen_count=r.reopen_count,
        scenario_run_id=r.scenario_run_id,
        source=ObservationSource(r.source),
    )


def _to_event(r: IncidentEventRecord) -> StoredEvent:
    actor = Actor(ActorType(r.actor_type), r.actor_label, r.actor_id)
    event = IncidentEvent(r.incident_id, EventType(r.event_type), actor, r.occurred_at, r.payload)
    return StoredEvent(r.id, event)


def _to_evidence(row: Any) -> StoredEvidence:
    return StoredEvidence(
        id=row["id"],
        ordinal=row["ordinal"],
        role=EvidenceRole(row["role"]),
        added_at=row["added_at"],
        evaluation_id=row["rule_evaluation_id"],
        sample_id=row["metric_sample_id"],
        log_id=row["log_event_id"],
    )
