"""One evaluation pass over elapsed sample slots (architecture §02.2 steps 4-5, rules.md P-07).

Rules are evaluated at every 5 s sample slot, not once per worker cycle: hysteresis counts
evaluations, so a cadence-bound count would make the state history depend on the clock speed.
The same observations therefore yield the same states in realtime and in accelerated mode.
"""

import bisect
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from app.core.observation import SAMPLE_INTERVAL, tick_of, tick_time
from app.health.domain.aggregation import (
    PlatformVerdict,
    RuleStanding,
    component_verdict,
    impacted_by,
    platform_verdict,
)
from app.health.domain.evaluation import Measurement, measure, measure_absence
from app.health.domain.hysteresis import RuleProgress, advance, target_state
from app.health.domain.rules import HealthRule
from app.health.domain.states import HealthState
from app.ingestion.domain.observations import ObservationMark, StoredSample
from app.topology.domain import Component, PlatformTopology

# Besides first evaluations and state changes, one evaluation per rule and component is kept
# per minute of platform time (architecture §03.1).
RECORD_EVERY = timedelta(seconds=60)


@dataclass(frozen=True, slots=True)
class EvaluationKey:
    """Natural key of an evaluation recorded in this pass, before the database assigns its ID."""

    component_id: uuid.UUID
    rule_id: uuid.UUID
    evaluated_at: datetime


type EvaluationRef = int | EvaluationKey


@dataclass(frozen=True, slots=True)
class RuleTrack:
    """Debounced state of one rule on one component and the evaluations that justify it."""

    progress: RuleProgress
    evaluated_at: datetime
    recorded_at: datetime
    last_evaluation: EvaluationRef
    state_evaluation: EvaluationRef


@dataclass(frozen=True, slots=True)
class Standing:
    """A stored component or platform state."""

    state: HealthState
    since: datetime


class ObservationIndex:
    """Stored observations per component (and metric), in observed_at order."""

    def __init__(self, samples: Iterable[StoredSample], marks: Iterable[ObservationMark]) -> None:
        self._samples: dict[tuple[uuid.UUID, str], list[StoredSample]] = defaultdict(list)
        for s in sorted(samples, key=lambda s: (s.observed_at, s.id)):
            self._samples[(s.component_id, s.metric_name)].append(s)
        self._marks: dict[uuid.UUID, list[ObservationMark]] = defaultdict(list)
        for m in sorted(marks, key=lambda m: m.observed_at):
            self._marks[m.component_id].append(m)
        self._sample_times = {k: [s.observed_at for s in v] for k, v in self._samples.items()}
        self._mark_times = {k: [m.observed_at for m in v] for k, v in self._marks.items()}

    def samples(
        self, component_id: uuid.UUID, metric_name: str, after: datetime, until: datetime
    ) -> list[StoredSample]:
        key = (component_id, metric_name)
        return _between(self._samples.get(key, []), self._sample_times.get(key, []), after, until)

    def marks(
        self, component_id: uuid.UUID, after: datetime, until: datetime
    ) -> list[ObservationMark]:
        return _between(
            self._marks.get(component_id, []), self._mark_times.get(component_id, []), after, until
        )


def applicable_pairs(
    components: Sequence[Component], rules: Sequence[HealthRule]
) -> list[tuple[Component, HealthRule]]:
    return [(c, r) for c in components for r in rules if r.applies_to(c)]


@dataclass(frozen=True, slots=True)
class EvaluationSlots:
    """Sample slots to evaluate, ascending; `skipped` slots fell beyond the bound."""

    slots: list[datetime]
    skipped: int


def slots_to_evaluate(
    pairs: Sequence[tuple[Component, HealthRule]],
    prior: Mapping[tuple[uuid.UUID, str], RuleTrack],
    until: datetime,
    max_slots: int,
) -> EvaluationSlots:
    """Sample slots up to `until` that some applicable rule has not evaluated, at most the last
    `max_slots` (older slots fall outside the ingestion lateness bound)."""
    newest = tick_of(until)
    seen = [prior[(c.id, r.key)].evaluated_at for c, r in pairs if (c.id, r.key) in prior]
    wanted = tick_of(min(seen)) + 1 if seen else newest
    first = max(wanted, newest - max_slots + 1)
    return EvaluationSlots([tick_time(t) for t in range(first, newest + 1)], max(0, first - wanted))


def _between[T](items: list[T], times: list[datetime], after: datetime, until: datetime) -> list[T]:
    return items[bisect.bisect_right(times, after) : bisect.bisect_right(times, until)]


@dataclass(frozen=True, slots=True)
class EvaluationPlan:
    """`ticks`: ascending sample slots to evaluate; `prior_rules` keyed by (component, rule key)."""

    topology: PlatformTopology
    rules: Sequence[HealthRule]
    ticks: Sequence[datetime]
    prior_rules: Mapping[tuple[uuid.UUID, str], RuleTrack]
    prior_components: Mapping[uuid.UUID, Standing]
    prior_platform: Standing | None
    observations: ObservationIndex


@dataclass(frozen=True, slots=True)
class RecordedEvaluation:
    component_id: uuid.UUID
    rule: HealthRule
    evaluated_at: datetime
    measurement: Measurement
    state: HealthState

    @property
    def key(self) -> EvaluationKey:
        return EvaluationKey(self.component_id, self.rule.id, self.evaluated_at)


@dataclass(frozen=True, slots=True)
class RuleSnapshot:
    component_id: uuid.UUID
    rule: HealthRule
    track: RuleTrack
    measurement: Measurement


@dataclass(frozen=True, slots=True)
class ComponentSnapshot:
    component_id: uuid.UUID
    state: HealthState
    since: datetime
    evaluated_at: datetime
    reason: EvaluationRef | None
    impacted_by: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class PlatformSnapshot:
    platform_id: uuid.UUID
    state: HealthState
    since: datetime
    evaluated_at: datetime
    verdict: PlatformVerdict


class Scope(StrEnum):
    RULE = "rule"
    COMPONENT = "component"
    PLATFORM = "platform"


@dataclass(frozen=True, slots=True)
class Transition:
    scope: Scope
    subject: str
    previous: HealthState | None
    current: HealthState
    at: datetime


@dataclass(frozen=True, slots=True)
class EvaluationPass:
    recorded: list[RecordedEvaluation]
    rules: list[RuleSnapshot]
    components: list[ComponentSnapshot]
    platform: PlatformSnapshot | None
    transitions: list[Transition]


@dataclass
class _Pass:
    plan: EvaluationPlan
    tracks: dict[tuple[uuid.UUID, str], RuleTrack]
    measured: dict[tuple[uuid.UUID, str], RuleSnapshot] = field(default_factory=dict)
    recorded: list[RecordedEvaluation] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)


def evaluate(plan: EvaluationPlan) -> EvaluationPass:
    """Evaluates each applicable rule at each slot it has not seen yet. A rule without history
    on a component starts at the newest slot: it never back-fills states it did not observe."""
    run = _Pass(plan, dict(plan.prior_rules))
    components = plan.topology.components
    pairs = applicable_pairs(components, plan.rules)
    states: dict[uuid.UUID, Standing | None] = {
        c.id: plan.prior_components.get(c.id) for c in components
    }
    platform, verdict = plan.prior_platform, None
    newest = plan.ticks[-1] if plan.ticks else None
    evaluated: set[uuid.UUID] = set()
    for at in plan.ticks:
        touched = {c.id for c, r in pairs if _evaluate_pair(run, c, r, at, at == newest)}
        for component in components:
            if component.id in touched:
                current = component_verdict(_standings(run, component)).state
                states[component.id] = _moved(
                    run, (Scope.COMPONENT, component.key), states[component.id], current, at
                )
        if touched:
            evaluated |= touched
            known = {cid: s.state for cid, s in states.items() if s is not None}
            verdict = platform_verdict(components, known)
            platform = _moved(run, (Scope.PLATFORM, plan.topology.key), platform, verdict.state, at)
    snapshot = None
    if newest is not None and platform is not None and verdict is not None:
        snapshot = PlatformSnapshot(
            plan.topology.platform_id, platform.state, platform.since, newest, verdict
        )
    return EvaluationPass(
        recorded=run.recorded,
        rules=list(run.measured.values()),
        components=[]
        if newest is None
        else _component_snapshots(run, {cid: states[cid] for cid in evaluated}, newest),
        platform=snapshot,
        transitions=run.transitions,
    )


def _evaluate_pair(
    run: _Pass, component: Component, rule: HealthRule, at: datetime, newest: bool
) -> bool:
    key = (component.id, rule.key)
    track = run.tracks.get(key)
    if (track is None and not newest) or (track is not None and track.evaluated_at >= at):
        return False
    measurement = _measure(run.plan.observations, component, rule, at)
    progress = RuleProgress.initial(at) if track is None else track.progress
    if track is not None and at - track.evaluated_at > SAMPLE_INTERVAL:
        # Debounce counts consecutive slots: a skipped stretch breaks any streak in progress.
        progress = RuleProgress(progress.state, progress.since)
    advanced = advance(
        rule.definition, progress, target_state(rule.definition, measurement, progress.state), at
    )
    changed = advanced.state is not progress.state
    if changed:
        subject = f"{component.key}/{rule.key}"
        run.transitions.append(Transition(Scope.RULE, subject, progress.state, advanced.state, at))
    if track is None or changed or at - track.recorded_at >= RECORD_EVERY:
        recorded = RecordedEvaluation(component.id, rule, at, measurement, advanced.state)
        run.recorded.append(recorded)
        state_ref = recorded.key if track is None or changed else track.state_evaluation
        track = RuleTrack(advanced, at, at, recorded.key, state_ref)
    else:
        track = RuleTrack(
            advanced, at, track.recorded_at, track.last_evaluation, track.state_evaluation
        )
    run.tracks[key] = track
    run.measured[key] = RuleSnapshot(component.id, rule, track, measurement)
    return True


def _measure(
    observations: ObservationIndex, component: Component, rule: HealthRule, at: datetime
) -> Measurement:
    after = at - timedelta(seconds=rule.definition.window_seconds)
    spec = rule.definition.measure
    if spec is None:
        return measure_absence(rule, observations.marks(component.id, after, at), at)
    return measure(rule, spec, observations.samples(component.id, spec.metric_name, after, at))


def _standings(run: _Pass, component: Component) -> list[RuleStanding]:
    """States of the rules that apply to the component now; dropped or retargeted rules no
    longer count."""
    applicable = {r.key for r in run.plan.rules if r.applies_to(component)}
    return [
        RuleStanding(rule_key, track.progress.state, track.progress.since)
        for (cid, rule_key), track in run.tracks.items()
        if cid == component.id and rule_key in applicable
    ]


def _moved(
    run: _Pass,
    subject: tuple[Scope, str],
    previous: Standing | None,
    state: HealthState,
    at: datetime,
) -> Standing:
    if previous is not None and previous.state is state:
        return previous
    before = None if previous is None else previous.state
    run.transitions.append(Transition(*subject, before, state, at))
    return Standing(state, at)


def _component_snapshots(
    run: _Pass, states: Mapping[uuid.UUID, Standing | None], evaluated_at: datetime
) -> list[ComponentSnapshot]:
    current = {cid: s for cid, s in states.items() if s is not None}
    impact = impacted_by(
        {cid: s.state for cid, s in current.items()}, run.plan.topology.dependencies
    )
    by_id = {c.id: c for c in run.plan.topology.components}
    snapshots = []
    for component_id, standing in current.items():
        deciding = component_verdict(_standings(run, by_id[component_id])).deciding_rule
        track = None if deciding is None else run.tracks[(component_id, deciding)]
        snapshots.append(
            ComponentSnapshot(
                component_id,
                standing.state,
                standing.since,
                evaluated_at,
                None if track is None else track.state_evaluation,
                impact.get(component_id, ()),
            )
        )
    return snapshots
