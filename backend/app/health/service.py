import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Protocol

import structlog
from sqlalchemy.orm import Session, sessionmaker

from app.core.observation import SAMPLE_INTERVAL
from app.core.retention import EvidenceHolds
from app.health.domain.engine import (
    EvaluationPlan,
    ObservationIndex,
    RecordedEvaluation,
    Scope,
    Standing,
    Transition,
    applicable_pairs,
    evaluate,
    slots_to_evaluate,
)
from app.health.domain.freshness import HealthView, ReadContext, health_view
from app.health.domain.hysteresis import required_streak
from app.health.domain.records import (
    EvaluationFilter,
    EvaluationOutcome,
    HealthPass,
    RuleCondition,
    StoredEvaluation,
    StoredRuleState,
)
from app.health.domain.rules import HealthRule, RuleSpec
from app.health.domain.states import HealthState
from app.health.repository import (
    HealthRuleRepository,
    HealthSnapshotRepository,
    RuleEvaluationRepository,
    RuleStateRepository,
    clear_health_state,
    purge_evaluations_before,
)
from app.ingestion.service import ObservationReader
from app.topology.domain import (
    Component,
    ComponentNotFoundError,
    PlatformNotFoundError,
    PlatformTopology,
)
from app.topology.service import TopologyService

log = structlog.get_logger(__name__)


class HealthRuleCatalog:
    """Stores the configured rules as immutable versions (D-08), idempotently."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def ensure(self, specs: Sequence[RuleSpec]) -> list[HealthRule]:
        """A new version for each changed rule and a disabled version for each rule no longer
        declared; returns the versions created."""
        with self._session_factory.begin() as session:
            rules = HealthRuleRepository(session, ObservationReader(session).units())
            latest = rules.latest()
            declared = {spec.key for spec in specs}
            changes = [
                s for s in specs if s.key not in latest or latest[s.key].definition != s.definition
            ]
            changes += [
                RuleSpec(r.key, replace(r.definition, enabled=False))
                for r in latest.values()
                if r.key not in declared and r.definition.enabled
            ]
            for spec in changes:
                previous = latest.get(spec.key)
                rules.add_version(spec, 1 if previous is None else previous.version + 1)
            stored = rules.latest()
        created = [stored[s.key] for s in changes]
        log.info(
            "health_rules.seeded",
            declared=len(specs),
            new_versions=[f"{r.key} v{r.version}" for r in created],
        )
        return created


class HistoryOrigin(Protocol):
    def history_start(self, session: Session) -> datetime | None:
        """Instant the current observation history starts after (the latest reset)."""
        ...


class HealthEvaluation:
    """Cycle steps 4-5 (architecture §02.2), inside the caller's unit of work."""

    def __init__(
        self,
        topology: TopologyService,
        platform_key: str,
        lookback: timedelta,
        origin: HistoryOrigin,
    ) -> None:
        self._topology_service = topology
        self._platform_key = platform_key
        self._lookback = lookback
        self._origin = origin
        self._topology: PlatformTopology | None = None

    def evaluate(self, session: Session, platform_now: datetime) -> HealthPass | None:
        """Evaluates every collected sample slot not evaluated yet; None when there is none or
        when the evaluation failed.

        Writes sit in a savepoint: a failing evaluation never rolls back the collection of the
        same cycle. Stored states then age, and reads report them Unknown once stale.
        """
        try:
            with session.begin_nested():
                return self._evaluate(session, platform_now)
        except Exception:
            # Health boundary (C-14), like a connector: the cycle goes on and the failure shows
            # as stale states, never as a silent green.
            log.exception("health.evaluation_failed", platform_time=platform_now)
            return None

    def _evaluate(self, session: Session, platform_now: datetime) -> HealthPass | None:
        topology = self._platform()
        component_ids = [c.id for c in topology.components]
        reader = ObservationReader(session)
        rules_repository = HealthRuleRepository(session, reader.units())
        rules = rules_repository.active()
        states = RuleStateRepository(session, rules_repository)
        pairs = applicable_pairs(topology.components, rules)
        states.keep_only(component_ids, {(c.id, r.key) for c, r in pairs})
        prior = states.tracks(component_ids)
        # A slot is evaluated once, so only once every connector has delivered it.
        collected = reader.collected_until()
        until = platform_now if collected is None else min(platform_now, collected)
        planned = slots_to_evaluate(pairs, prior, until, self._max_slots)
        if planned.skipped:
            log.warning("health.slots_skipped", slots=planned.skipped, resumed_at=planned.slots[0])
        # ADR 0017: a reset keeps the observations cited as incident evidence. Neither they
        # nor the slots they cover belong to the history that restarted.
        origin = self._origin.history_start(session)
        slots = [s for s in planned.slots if origin is None or s > origin]
        if not slots:
            return None
        snapshots = HealthSnapshotRepository(session)
        stored_platform = snapshots.platform(topology.platform_id)
        plan = EvaluationPlan(
            topology=topology,
            rules=rules,
            ticks=slots,
            prior_rules=prior,
            prior_components={
                cid: s.standing for cid, s in snapshots.components(component_ids).items()
            },
            prior_platform=None if stored_platform is None else stored_platform.standing,
            observations=self._observations(reader, component_ids, rules, slots, origin),
        )
        result = evaluate(plan)
        ids = RuleEvaluationRepository(session, rules_repository).insert(result.recorded)
        states.save(result.rules, ids)
        snapshots.save_components(result.components, ids)
        if result.platform is not None:
            snapshots.save_platform(result.platform)
        for transition in result.transitions:
            _log_transition(transition)
        return HealthPass(
            history_start=origin,
            rules=tuple(rules),
            before={k: RuleCondition(t.progress.state, t.raw_state) for k, t in prior.items()},
            outcomes=tuple(_outcome(e, ids[e.key]) for e in result.recorded),
        )

    @property
    def _max_slots(self) -> int:
        return max(1, self._lookback // SAMPLE_INTERVAL)

    @staticmethod
    def _observations(
        reader: ObservationReader,
        component_ids: Sequence[uuid.UUID],
        rules: Sequence[HealthRule],
        slots: Sequence[datetime],
        origin: datetime | None,
    ) -> ObservationIndex:
        """Everything the windows of these slots cover after `origin`, one bounded read per
        metric."""

        def bounded(after: datetime) -> datetime:
            return after if origin is None else max(after, origin)

        lookback: dict[str, datetime] = {}
        absence_window = 0
        for rule in rules:
            window = rule.definition.window_seconds
            if rule.definition.measure is None:
                absence_window = max(absence_window, window)
                continue
            after = bounded(slots[0] - timedelta(seconds=window))
            metric = rule.definition.measure.metric_name
            lookback[metric] = min(after, lookback.get(metric, after))
        marks = (
            reader.marks(
                component_ids, bounded(slots[0] - timedelta(seconds=absence_window)), slots[-1]
            )
            if absence_window
            else []
        )
        return ObservationIndex(reader.samples(component_ids, lookback, slots[-1]), marks)

    def _platform(self) -> PlatformTopology:
        # Components and dependencies only change at seed time, before the worker starts.
        if self._topology is None:
            topology = self._topology_service.platform(self._platform_key)
            if topology is None:
                raise PlatformNotFoundError(f"Platform {self._platform_key} is not seeded.")
            self._topology = topology
        return self._topology


def _outcome(e: RecordedEvaluation, evaluation_id: int) -> EvaluationOutcome:
    return EvaluationOutcome(
        id=evaluation_id,
        component_id=e.component_id,
        rule=e.rule,
        evaluated_at=e.evaluated_at,
        state=e.state,
        raw_state=e.measurement.raw_state,
        sets_state=e.sets_state,
        evidence=e.measurement.evidence,
    )


def _log_transition(t: Transition) -> None:
    event = {
        Scope.RULE: "health.rule_state_changed",
        Scope.COMPONENT: "health.component_state_changed",
        Scope.PLATFORM: "health.platform_state_changed",
    }[t.scope]
    log.info(event, subject=t.subject, previous=t.previous, state=t.current, platform_time=t.at)


class HealthHistory:
    """Health-state writes in the caller's unit of work, for other modules' use cases."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def clear(self, holds: EvidenceHolds) -> int:
        """Forgets every derived state and every evaluation but held evidence, as when
        observations are purged: states restart from Unknown instead of carrying hysteresis
        over a history that is gone."""
        return clear_health_state(self._session, holds.evaluations)


class HealthReader:
    """Health reads in the caller's unit of work, for other modules' use cases."""

    def __init__(self, session: Session) -> None:
        self._rules = HealthRuleRepository(session, ObservationReader(session).units())
        self._session = session

    def active_rules(self) -> list[HealthRule]:
        return self._rules.active()

    def rule_states(self, component_id: uuid.UUID) -> list[StoredRuleState]:
        """Current debounced state and latest measurement of each rule on the component."""
        return RuleStateRepository(self._session, self._rules).of_component(component_id)

    def evaluations(self, ids: Sequence[int]) -> dict[int, StoredEvaluation]:
        if not ids:
            return {}
        return RuleEvaluationRepository(self._session, self._rules).get_many(ids)


def purge_evaluations(session: Session, cutoff: datetime, batch: int, holds: EvidenceHolds) -> int:
    """Retention of evaluations no current state cites and no hold keeps (ADR 0008)."""
    return purge_evaluations_before(session, cutoff, batch, holds.evaluations)


@dataclass(frozen=True, slots=True)
class ComponentRef:
    id: uuid.UUID
    key: str


@dataclass(frozen=True, slots=True)
class PlatformHealthView:
    topology: PlatformTopology
    health: HealthView
    counts: dict[HealthState, int]
    priority: int | None
    rationale: str
    decided_by: tuple[ComponentRef, ...]


@dataclass(frozen=True, slots=True)
class ComponentHealthView:
    platform_id: uuid.UUID
    component: Component
    health: HealthView
    reason: StoredEvaluation | None
    impacted_by: tuple[ComponentRef, ...]


@dataclass(frozen=True, slots=True)
class RuleStatusView:
    state: StoredRuleState
    health: HealthView
    required_streak: int | None


@dataclass(frozen=True, slots=True)
class TopologyView:
    platform: PlatformHealthView
    components: list[ComponentHealthView]


class HealthQueries:
    """Read side for the API; stale stored states are reported Unknown (D-02).

    Each answer reads its snapshots in one session, so it never mixes two worker cycles.
    """

    def __init__(self, session_factory: sessionmaker[Session], topology: TopologyService) -> None:
        self._session_factory = session_factory
        self._topology = topology

    def platforms(self, context: ReadContext) -> list[PlatformHealthView]:
        topologies = self._topology.platforms()
        with self._session_factory() as session:
            return [_platform_view(session, t, context) for t in topologies]

    def topology(self, platform_id: uuid.UUID, context: ReadContext) -> TopologyView:
        topology = self._platform_topology(platform_id)
        with self._session_factory() as session:
            return TopologyView(
                _platform_view(session, topology, context),
                _component_views(session, topology, topology.components, context),
            )

    def components(
        self, platform_id: uuid.UUID | None, context: ReadContext
    ) -> list[ComponentHealthView]:
        topologies = self._topology.platforms()
        if platform_id is not None:
            topologies = [t for t in topologies if t.platform_id == platform_id]
        with self._session_factory() as session:
            return [
                view
                for topology in topologies
                for view in _component_views(session, topology, topology.components, context)
            ]

    def component(
        self, component_id: uuid.UUID, context: ReadContext
    ) -> tuple[ComponentHealthView, PlatformTopology]:
        topology = self._owning_platform(component_id)
        component = topology.component_by_id(component_id)
        with self._session_factory() as session:
            (view,) = _component_views(session, topology, [component], context)
        return view, topology

    def component_rules(
        self, component_id: uuid.UUID, context: ReadContext
    ) -> tuple[ComponentHealthView, list[RuleStatusView]]:
        topology = self._owning_platform(component_id)
        component = topology.component_by_id(component_id)
        with self._session_factory() as session:
            (view,) = _component_views(session, topology, [component], context)
            rules = HealthRuleRepository(session, ObservationReader(session).units())
            states = RuleStateRepository(session, rules).of_component(component_id)
        return view, [
            RuleStatusView(
                s,
                health_view(Standing(s.progress.state, s.progress.since), s.evaluated_at, context),
                required_streak(s.rule.definition, s.progress),
            )
            for s in states
        ]

    def rules(self, all_versions: bool) -> list[HealthRule]:
        with self._session_factory() as session:
            rules = HealthRuleRepository(session, ObservationReader(session).units())
            return rules.versions() if all_versions else rules.active()

    def evaluations(self, query: EvaluationFilter) -> list[StoredEvaluation]:
        if query.component_id is not None:
            self._owning_platform(query.component_id)
        with self._session_factory() as session:
            rules = HealthRuleRepository(session, ObservationReader(session).units())
            return RuleEvaluationRepository(session, rules).page(query)

    def component_keys(self) -> dict[uuid.UUID, str]:
        return {c.id: c.key for t in self._topology.platforms() for c in t.components}

    def _platform_topology(self, platform_id: uuid.UUID) -> PlatformTopology:
        found = next((t for t in self._topology.platforms() if t.platform_id == platform_id), None)
        if found is None:
            raise PlatformNotFoundError(f"No platform {platform_id}.")
        return found

    def _owning_platform(self, component_id: uuid.UUID) -> PlatformTopology:
        for topology in self._topology.platforms():
            if any(c.id == component_id for c in topology.components):
                return topology
        raise ComponentNotFoundError(f"No component {component_id}.")


def _component_views(
    session: Session,
    topology: PlatformTopology,
    components: Sequence[Component],
    context: ReadContext,
) -> list[ComponentHealthView]:
    refs = {c.id: ComponentRef(c.id, c.key) for c in topology.components}
    stored = HealthSnapshotRepository(session).components([c.id for c in components])
    reason_ids = [s.reason_evaluation_id for s in stored.values() if s.reason_evaluation_id]
    rules = HealthRuleRepository(session, ObservationReader(session).units())
    reasons = RuleEvaluationRepository(session, rules).get_many(reason_ids)
    views = []
    for component in components:
        health = stored.get(component.id)
        if health is None:
            views.append(
                ComponentHealthView(
                    topology.platform_id, component, health_view(None, None, context), None, ()
                )
            )
            continue
        reason = health.reason_evaluation_id
        views.append(
            ComponentHealthView(
                topology.platform_id,
                component,
                health_view(health.standing, health.evaluated_at, context),
                None if reason is None else reasons.get(reason),
                tuple(refs[i] for i in health.impacted_by if i in refs),
            )
        )
    return views


def _platform_view(
    session: Session, topology: PlatformTopology, context: ReadContext
) -> PlatformHealthView:
    stored = HealthSnapshotRepository(session).platform(topology.platform_id)
    refs = {c.id: ComponentRef(c.id, c.key) for c in topology.components}
    if stored is None:
        return PlatformHealthView(
            topology,
            health_view(None, None, context),
            dict.fromkeys(HealthState, 0),
            None,
            "Not evaluated yet.",
            (),
        )
    return PlatformHealthView(
        topology,
        health_view(stored.standing, stored.evaluated_at, context),
        {s: stored.counts.get(s, 0) for s in HealthState},
        stored.priority,
        stored.rationale,
        tuple(refs[i] for i in stored.decided_by if i in refs),
    )
