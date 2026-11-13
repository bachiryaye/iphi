import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, cast

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Double,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Select,
    SmallInteger,
    String,
    UniqueConstraint,
    delete,
    func,
    literal,
    select,
    tuple_,
    union,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.sql.selectable import CompoundSelect
from sqlalchemy.types import Uuid

from app.core.db import Base, check_in
from app.health.domain.engine import (
    ComponentSnapshot,
    EvaluationKey,
    EvaluationRef,
    PlatformSnapshot,
    RecordedEvaluation,
    RuleSnapshot,
    RuleTrack,
    Standing,
)
from app.health.domain.evaluation import Evidence, Measurement
from app.health.domain.hysteresis import RuleProgress
from app.health.domain.records import (
    EvaluationFilter,
    StoredComponentHealth,
    StoredEvaluation,
    StoredPlatformHealth,
    StoredRuleState,
)
from app.health.domain.rules import (
    MAX_TEXT_CHARS,
    Aggregation,
    FailureClass,
    HealthRule,
    Level,
    Measure,
    Operator,
    RuleDefinition,
    RuleSpec,
    RuleType,
    TargetSelector,
)
from app.health.domain.states import HealthState
from app.topology.domain import ComponentType

MAX_EXPLANATION_CHARS = 512
_STATE = check_in("state", HealthState)


class HealthRuleRecord(Base):
    """Rule versions; immutable (D-08), a trigger of migration 0004 rejects UPDATE and DELETE."""

    __tablename__ = "health_rule"
    __table_args__ = (
        UniqueConstraint("key", "version"),
        CheckConstraint(check_in("rule_type", RuleType), name="rule_type"),
        CheckConstraint(check_in("failure_class", FailureClass), name="failure_class"),
        CheckConstraint(
            f"aggregation IS NULL OR {check_in('aggregation', Aggregation)}", name="aggregation"
        ),
        CheckConstraint(f"operator IS NULL OR {check_in('operator', Operator)}", name="operator"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("window_seconds > 0", name="window_positive"),
        CheckConstraint(
            "raise_after >= 1 AND clear_after >= 1 AND min_samples >= 1", name="counts_positive"
        ),
        CheckConstraint(
            "(metric_name IS NULL) = (rule_type = 'absence') "
            "AND (metric_name IS NULL) = (aggregation IS NULL) "
            "AND (metric_name IS NULL) = (operator IS NULL)",
            name="measure_complete",
        ),
        CheckConstraint(
            "(warning_threshold IS NULL) = (warning_clear IS NULL) "
            "AND (critical_threshold IS NULL) = (critical_clear IS NULL)",
            name="levels_complete",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    key: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column(Integer)
    rule_type: Mapped[str] = mapped_column(String(32))
    failure_class: Mapped[str] = mapped_column(String(32))
    target_selector: Mapped[dict[str, list[str]]] = mapped_column(JSONB)
    metric_name: Mapped[str | None] = mapped_column(ForeignKey("metric_definition.metric_name"))
    aggregation: Mapped[str | None] = mapped_column(String(16))
    window_seconds: Mapped[int] = mapped_column(Integer)
    operator: Mapped[str | None] = mapped_column(String(8))
    warning_threshold: Mapped[float | None] = mapped_column(Double)
    critical_threshold: Mapped[float | None] = mapped_column(Double)
    warning_clear: Mapped[float | None] = mapped_column(Double)
    critical_clear: Mapped[float | None] = mapped_column(Double)
    raise_after: Mapped[int] = mapped_column(SmallInteger)
    clear_after: Mapped[int] = mapped_column(SmallInteger)
    min_samples: Mapped[int] = mapped_column(SmallInteger)
    rationale: Mapped[str] = mapped_column(String(MAX_TEXT_CHARS))
    recommendation: Mapped[str] = mapped_column(String(MAX_TEXT_CHARS))
    enabled: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class RuleEvaluationRecord(Base):
    __tablename__ = "rule_evaluation"
    __table_args__ = (
        # One evaluation per rule version, component and sample slot.
        UniqueConstraint("component_id", "rule_id", "evaluated_at"),
        CheckConstraint(_STATE, name="state"),
        CheckConstraint(check_in("raw_state", HealthState), name="raw_state"),
        CheckConstraint("sample_count >= 0", name="sample_count_non_negative"),
        CheckConstraint("window_start < evaluated_at", name="window_ordered"),
        Index("ix_rule_evaluation_component_id_evaluated_at", "component_id", "evaluated_at"),
        Index("ix_rule_evaluation_rule_id_evaluated_at", "rule_id", "evaluated_at"),
        # Serves unfiltered newest-first pages (keyset on evaluated_at, id) and retention.
        Index("ix_rule_evaluation_evaluated_at_id", "evaluated_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("health_rule.id"))
    component_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("component.id"))
    evaluated_at: Mapped[datetime]
    window_start: Mapped[datetime]
    observed_value: Mapped[float | None] = mapped_column(Double)
    sample_count: Mapped[int] = mapped_column(Integer)
    raw_state: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16))
    explanation: Mapped[str] = mapped_column(String(MAX_EXPLANATION_CHARS))
    evidence: Mapped[dict[str, list[int]]] = mapped_column(JSONB)


class RuleStateRecord(Base):
    """Hysteresis state and latest evaluation of a rule on a component; persists restarts."""

    __tablename__ = "rule_state"
    __table_args__ = (
        CheckConstraint(_STATE, name="state"),
        CheckConstraint(check_in("raw_state", HealthState), name="raw_state"),
        CheckConstraint(
            f"pending_state IS NULL OR {check_in('pending_state', HealthState)}",
            name="pending_state",
        ),
        CheckConstraint("(pending_state IS NULL) = (raw_streak = 0)", name="streak_pending"),
    )

    component_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("component.id"), primary_key=True)
    rule_key: Mapped[str] = mapped_column(String(16), primary_key=True)
    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("health_rule.id"))
    state: Mapped[str] = mapped_column(String(16))
    since: Mapped[datetime]
    pending_state: Mapped[str | None] = mapped_column(String(16))
    raw_streak: Mapped[int] = mapped_column(SmallInteger)
    raw_state: Mapped[str] = mapped_column(String(16))
    observed_value: Mapped[float | None] = mapped_column(Double)
    sample_count: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(String(MAX_EXPLANATION_CHARS))
    evidence: Mapped[dict[str, list[int]]] = mapped_column(JSONB)
    last_evaluated_at: Mapped[datetime]
    last_evaluation_id: Mapped[int] = mapped_column(ForeignKey("rule_evaluation.id"))
    state_evaluation_id: Mapped[int] = mapped_column(ForeignKey("rule_evaluation.id"))


class ComponentHealthRecord(Base):
    __tablename__ = "component_health"
    __table_args__ = (CheckConstraint(_STATE, name="state"),)

    component_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("component.id"), primary_key=True)
    state: Mapped[str] = mapped_column(String(16))
    since: Mapped[datetime]
    last_evaluated_at: Mapped[datetime]
    reason_evaluation_id: Mapped[int | None] = mapped_column(ForeignKey("rule_evaluation.id"))
    impacted_by: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid()))


class PlatformHealthRecord(Base):
    __tablename__ = "platform_health"
    __table_args__ = (
        CheckConstraint(_STATE, name="state"),
        CheckConstraint("priority IS NULL OR priority BETWEEN 1 AND 4", name="priority"),
    )

    platform_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.id"), primary_key=True)
    state: Mapped[str] = mapped_column(String(16))
    since: Mapped[datetime]
    last_evaluated_at: Mapped[datetime]
    counts: Mapped[dict[str, int]] = mapped_column(JSONB)
    priority: Mapped[int | None] = mapped_column(SmallInteger)
    rationale: Mapped[str] = mapped_column(String(MAX_EXPLANATION_CHARS))
    decided_by: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid()))


class HealthRuleRepository:
    """`units`: canonical unit per metric, from the metric catalog (D-15)."""

    def __init__(self, session: Session, units: Mapping[str, str]) -> None:
        self._session = session
        self._units = units

    def add_version(self, spec: RuleSpec, version: int) -> None:
        self._session.add(_rule_record(spec, version))
        self._session.flush()

    def latest(self) -> dict[str, HealthRule]:
        """Latest version of every rule key, enabled or not."""
        newest = (
            select(HealthRuleRecord.key, func.max(HealthRuleRecord.version).label("version"))
            .group_by(HealthRuleRecord.key)
            .subquery()
        )
        statement = select(HealthRuleRecord).join(
            newest,
            (HealthRuleRecord.key == newest.c.key) & (HealthRuleRecord.version == newest.c.version),
        )
        return {r.key: r for r in self._rules(statement)}

    def active(self) -> list[HealthRule]:
        """Latest version of every enabled rule, by key."""
        return sorted((r for r in self.latest().values() if r.definition.enabled), key=_by_key)

    def versions(self) -> list[HealthRule]:
        statement = select(HealthRuleRecord).order_by(
            HealthRuleRecord.key, HealthRuleRecord.version
        )
        return self._rules(statement)

    def by_ids(self, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, HealthRule]:
        statement = select(HealthRuleRecord).where(HealthRuleRecord.id.in_(ids))
        return {r.id: r for r in self._rules(statement)}

    def _rules(self, statement: Select[HealthRuleRecord]) -> list[HealthRule]:
        return [
            _to_rule(r, None if r.metric_name is None else self._units.get(r.metric_name))
            for r in self._session.scalars(statement)
        ]


def _by_key(rule: HealthRule) -> str:
    return rule.key


def _rule_record(spec: RuleSpec, version: int) -> HealthRuleRecord:
    d = spec.definition
    m = d.measure
    return HealthRuleRecord(
        key=spec.key,
        version=version,
        rule_type=d.rule_type.value,
        failure_class=d.failure_class.value,
        target_selector={
            "types": sorted(t.value for t in d.targets.component_types),
            "components": sorted(d.targets.component_keys),
        },
        metric_name=None if m is None else m.metric_name,
        aggregation=None if m is None else m.aggregation.value,
        window_seconds=d.window_seconds,
        operator=None if m is None else m.operator.value,
        warning_threshold=None if m is None or m.warning is None else m.warning.threshold,
        warning_clear=None if m is None or m.warning is None else m.warning.clear,
        critical_threshold=None if m is None or m.critical is None else m.critical.threshold,
        critical_clear=None if m is None or m.critical is None else m.critical.clear,
        raise_after=d.raise_after,
        clear_after=d.clear_after,
        min_samples=d.min_samples,
        rationale=d.rationale,
        recommendation=d.recommendation,
        enabled=d.enabled,
    )


def _to_rule(r: HealthRuleRecord, unit: str | None) -> HealthRule:
    measure = None
    if r.metric_name is not None and r.aggregation is not None and r.operator is not None:
        measure = Measure(
            r.metric_name,
            Aggregation(r.aggregation),
            Operator(r.operator),
            _level(r.warning_threshold, r.warning_clear),
            _level(r.critical_threshold, r.critical_clear),
        )
    definition = RuleDefinition(
        rule_type=RuleType(r.rule_type),
        failure_class=FailureClass(r.failure_class),
        targets=TargetSelector(
            frozenset(ComponentType(t) for t in r.target_selector.get("types", [])),
            frozenset(r.target_selector.get("components", [])),
        ),
        measure=measure,
        window_seconds=r.window_seconds,
        raise_after=r.raise_after,
        clear_after=r.clear_after,
        min_samples=r.min_samples,
        rationale=r.rationale,
        recommendation=r.recommendation,
        enabled=r.enabled,
    )
    return HealthRule(r.id, r.key, r.version, definition, unit, r.created_at)


def _level(threshold: float | None, clear: float | None) -> Level | None:
    return None if threshold is None or clear is None else Level(threshold, clear)


class RuleEvaluationRepository:
    def __init__(self, session: Session, rules: HealthRuleRepository) -> None:
        self._session = session
        self._rules = rules

    def insert(self, evaluations: Sequence[RecordedEvaluation]) -> dict[EvaluationKey, int]:
        """IDs of the inserted evaluations, by natural key."""
        if not evaluations:
            return {}
        rows = [
            {
                "rule_id": e.rule.id,
                "component_id": e.component_id,
                "evaluated_at": e.evaluated_at,
                "window_start": e.evaluated_at - _window(e.rule),
                **_measurement_columns(e.measurement),
                "state": e.state.value,
            }
            for e in evaluations
        ]
        statement = insert(RuleEvaluationRecord).returning(
            RuleEvaluationRecord.id, sort_by_parameter_order=True
        )
        ids = self._session.scalars(statement, rows).all()
        return {e.key: i for e, i in zip(evaluations, ids, strict=True)}

    def page(self, query: EvaluationFilter) -> list[StoredEvaluation]:
        """Newest first, keyset on (evaluated_at, id)."""
        record = RuleEvaluationRecord
        statement = select(record, HealthRuleRecord.key).join(
            HealthRuleRecord, HealthRuleRecord.id == record.rule_id
        )
        statement = statement.where(
            record.evaluated_at >= query.start, record.evaluated_at < query.end
        )
        if query.component_id is not None:
            statement = statement.where(record.component_id == query.component_id)
        if query.rule_key is not None:
            statement = statement.where(HealthRuleRecord.key == query.rule_key)
        if query.state is not None:
            statement = statement.where(record.state == query.state.value)
        if query.before is not None:
            statement = statement.where(
                tuple_(record.evaluated_at, record.id)
                < tuple_(literal(query.before.evaluated_at), literal(query.before.id))
            )
        statement = statement.order_by(record.evaluated_at.desc(), record.id.desc()).limit(
            query.limit
        )
        records = [row[0] for row in self._session.execute(statement)]
        rules = self._rules.by_ids(list({r.rule_id for r in records}))
        return [_to_evaluation(r, rules[r.rule_id]) for r in records]

    def get_many(self, ids: Sequence[int]) -> dict[int, StoredEvaluation]:
        records = list(
            self._session.scalars(
                select(RuleEvaluationRecord).where(RuleEvaluationRecord.id.in_(ids))
            )
        )
        rules = self._rules.by_ids(list({r.rule_id for r in records}))
        return {r.id: _to_evaluation(r, rules[r.rule_id]) for r in records}


def purge_evaluations_before(session: Session, cutoff: datetime, batch: int) -> int:
    """Deletes at most `batch` evaluations older than `cutoff` that no current state cites."""
    record = RuleEvaluationRecord
    cited: CompoundSelect[tuple[int]] = union(
        select(RuleStateRecord.last_evaluation_id),
        select(RuleStateRecord.state_evaluation_id),
        select(ComponentHealthRecord.reason_evaluation_id).where(
            ComponentHealthRecord.reason_evaluation_id.is_not(None)
        ),
    )
    # TODO(US-05): also keep evaluations cited as incident evidence.
    oldest = (
        select(record.id).where(record.evaluated_at < cutoff, record.id.not_in(cited)).limit(batch)
    )
    result = session.execute(delete(record).where(record.id.in_(oldest.scalar_subquery())))
    return cast(CursorResult[Any], result).rowcount


def _window(rule: HealthRule) -> timedelta:
    return timedelta(seconds=rule.definition.window_seconds)


def _measurement_columns(m: Measurement) -> dict[str, Any]:
    return {
        "observed_value": m.observed_value,
        "sample_count": m.sample_count,
        "raw_state": m.raw_state.value,
        "explanation": m.explanation[:MAX_EXPLANATION_CHARS],
        "evidence": {"samples": list(m.evidence.sample_ids), "logs": list(m.evidence.log_ids)},
    }


def _measurement(
    raw_state: str,
    observed_value: float | None,
    sample_count: int,
    evidence: Mapping[str, list[int]],
    explanation: str,
) -> Measurement:
    return Measurement(
        HealthState(raw_state),
        observed_value,
        sample_count,
        Evidence(tuple(evidence.get("samples", [])), tuple(evidence.get("logs", []))),
        explanation,
    )


def _to_evaluation(r: RuleEvaluationRecord, rule: HealthRule) -> StoredEvaluation:
    return StoredEvaluation(
        id=r.id,
        rule=rule,
        component_id=r.component_id,
        evaluated_at=r.evaluated_at,
        window_start=r.window_start,
        measurement=_measurement(
            r.raw_state, r.observed_value, r.sample_count, r.evidence, r.explanation
        ),
        state=HealthState(r.state),
    )


class RuleStateRepository:
    def __init__(self, session: Session, rules: HealthRuleRepository) -> None:
        self._session = session
        self._rules = rules

    def tracks(self, component_ids: Sequence[uuid.UUID]) -> dict[tuple[uuid.UUID, str], RuleTrack]:
        """Hysteresis state per (component, rule key), with the time of its last recorded
        evaluation, which paces the once-a-minute recording."""
        statement = (
            select(RuleStateRecord, RuleEvaluationRecord.evaluated_at)
            .join(
                RuleEvaluationRecord, RuleEvaluationRecord.id == RuleStateRecord.last_evaluation_id
            )
            .where(RuleStateRecord.component_id.in_(component_ids))
        )
        return {
            (r.component_id, r.rule_key): RuleTrack(
                _progress(r), r.last_evaluated_at, recorded_at, r.last_evaluation_id,
                r.state_evaluation_id,
            )
            for r, recorded_at in self._session.execute(statement)
        }  # fmt: skip

    def save(self, snapshots: Sequence[RuleSnapshot], ids: Mapping[EvaluationKey, int]) -> None:
        if not snapshots:
            return
        rows = [
            {
                "component_id": s.component_id,
                "rule_key": s.rule.key,
                "rule_id": s.rule.id,
                "state": s.track.progress.state.value,
                "since": s.track.progress.since,
                "pending_state": None
                if s.track.progress.pending is None
                else s.track.progress.pending.value,
                "raw_streak": s.track.progress.streak,
                **_measurement_columns(s.measurement),
                "last_evaluated_at": s.track.evaluated_at,
                "last_evaluation_id": resolve(s.track.last_evaluation, ids),
                "state_evaluation_id": resolve(s.track.state_evaluation, ids),
            }
            for s in snapshots
        ]
        statement = insert(RuleStateRecord)
        updated = {c: statement.excluded[c] for c in rows[0] if c not in _RULE_STATE_KEY}
        self._session.execute(
            statement.on_conflict_do_update(index_elements=list(_RULE_STATE_KEY), set_=updated),
            rows,
        )

    def keep_only(
        self, component_ids: Sequence[uuid.UUID], pairs: set[tuple[uuid.UUID, str]]
    ) -> int:
        """Deletes states of these components' (component, rule) pairs no longer applicable: a
        disabled or retargeted rule stops counting for the component."""
        statement = delete(RuleStateRecord).where(RuleStateRecord.component_id.in_(component_ids))
        if pairs:
            kept = [tuple_(literal(c), literal(k)) for c, k in sorted(pairs)]
            statement = statement.where(
                tuple_(RuleStateRecord.component_id, RuleStateRecord.rule_key).not_in(kept)
            )
        result = self._session.execute(statement)
        return cast(CursorResult[Any], result).rowcount

    def of_component(self, component_id: uuid.UUID) -> list[StoredRuleState]:
        records = list(
            self._session.scalars(
                select(RuleStateRecord)
                .where(RuleStateRecord.component_id == component_id)
                .order_by(RuleStateRecord.rule_key)
            )
        )
        rules = self._rules.by_ids(list({r.rule_id for r in records}))
        return [
            StoredRuleState(
                component_id=r.component_id,
                rule=rules[r.rule_id],
                progress=_progress(r),
                measurement=_measurement(
                    r.raw_state, r.observed_value, r.sample_count, r.evidence, r.explanation
                ),
                evaluated_at=r.last_evaluated_at,
                last_evaluation_id=r.last_evaluation_id,
                state_evaluation_id=r.state_evaluation_id,
            )
            for r in records
        ]


_RULE_STATE_KEY = ("component_id", "rule_key")


def resolve(ref: EvaluationRef, ids: Mapping[EvaluationKey, int]) -> int:
    """Database ID of an evaluation, recorded earlier or in this pass."""
    return ref if isinstance(ref, int) else ids[ref]


def _progress(r: RuleStateRecord) -> RuleProgress:
    pending = None if r.pending_state is None else HealthState(r.pending_state)
    return RuleProgress(HealthState(r.state), r.since, pending, r.raw_streak)


class HealthSnapshotRepository:
    """Derived current states of components and platforms (architecture §03.1)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def components(
        self, component_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, StoredComponentHealth]:
        records = self._session.scalars(
            select(ComponentHealthRecord).where(
                ComponentHealthRecord.component_id.in_(component_ids)
            )
        )
        return {
            r.component_id: StoredComponentHealth(
                r.component_id,
                Standing(HealthState(r.state), r.since),
                r.last_evaluated_at,
                r.reason_evaluation_id,
                tuple(r.impacted_by),
            )
            for r in records
        }

    def platform(self, platform_id: uuid.UUID) -> StoredPlatformHealth | None:
        r = self._session.get(PlatformHealthRecord, platform_id)
        if r is None:
            return None
        return StoredPlatformHealth(
            r.platform_id,
            Standing(HealthState(r.state), r.since),
            r.last_evaluated_at,
            MappingProxyType({HealthState(k): v for k, v in r.counts.items()}),
            r.priority,
            r.rationale,
            tuple(r.decided_by),
        )

    def save_components(
        self, snapshots: Sequence[ComponentSnapshot], ids: Mapping[EvaluationKey, int]
    ) -> None:
        if not snapshots:
            return
        rows = [
            {
                "component_id": s.component_id,
                "state": s.state.value,
                "since": s.since,
                "last_evaluated_at": s.evaluated_at,
                "reason_evaluation_id": None if s.reason is None else resolve(s.reason, ids),
                "impacted_by": list(s.impacted_by),
            }
            for s in snapshots
        ]
        statement = insert(ComponentHealthRecord)
        updated = {c: statement.excluded[c] for c in rows[0] if c != "component_id"}
        self._session.execute(
            statement.on_conflict_do_update(index_elements=["component_id"], set_=updated), rows
        )

    def save_platform(self, snapshot: PlatformSnapshot) -> None:
        verdict = snapshot.verdict
        values = {
            "state": snapshot.state.value,
            "since": snapshot.since,
            "last_evaluated_at": snapshot.evaluated_at,
            "counts": {s.value: n for s, n in verdict.counts.items()},
            "priority": verdict.priority,
            "rationale": verdict.rationale[:MAX_EXPLANATION_CHARS],
            "decided_by": list(verdict.decided_by),
        }
        statement = insert(PlatformHealthRecord).values(platform_id=snapshot.platform_id, **values)
        self._session.execute(
            statement.on_conflict_do_update(index_elements=["platform_id"], set_=values)
        )


def clear_health_state(session: Session) -> int:
    """Deletes every derived state and evaluation; rule versions stay. Returns evaluations."""
    for record in (ComponentHealthRecord, PlatformHealthRecord, RuleStateRecord):
        session.execute(delete(record))
    result = session.execute(delete(RuleEvaluationRecord))
    return cast(CursorResult[Any], result).rowcount
