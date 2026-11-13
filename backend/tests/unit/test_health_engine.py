import uuid
from collections.abc import Sequence
from datetime import datetime

import pytest

from app.health.domain.engine import (
    EvaluationPass,
    EvaluationPlan,
    ObservationIndex,
    RecordedEvaluation,
    RuleTrack,
    Scope,
    Standing,
    applicable_pairs,
    evaluate,
    slots_to_evaluate,
)
from app.health.domain.hysteresis import RuleProgress
from app.health.domain.rules import HealthRule
from app.health.domain.states import HealthState
from app.ingestion.domain.observations import ObservationMark
from app.topology.domain import (
    Component,
    ComponentType,
    Criticality,
    Dependency,
    DependencyKind,
    PlatformTopology,
)
from tests.health_rules import SLOT, T0, absence_rule, latency_rule, sample

H, W, C, U = HealthState.HEALTHY, HealthState.WARNING, HealthState.CRITICAL, HealthState.UNKNOWN
GATEWAY = Component(uuid.uuid4(), "gw", "Gateway", ComponentType.GATEWAY, Criticality.HIGH)
API = Component(uuid.uuid4(), "api", "API", ComponentType.API, Criticality.MEDIUM)
TOPOLOGY = PlatformTopology(
    uuid.uuid4(),
    "plant",
    "Plant",
    "simulation",
    (GATEWAY, API),
    (Dependency(API.id, GATEWAY.id, DependencyKind.DATA_FLOW),),
)
RULES = (latency_rule(), absence_rule())
SLOTS = [T0 + i * SLOT for i in range(1, 61)]
# The gateway slows down in two steps of one minute each, then recovers; the API stays fast.
LATENCY = [60.0] * 12 + [400.0] * 12 + [1500.0] * 12 + [60.0] * 24


def observations() -> ObservationIndex:
    samples = [sample(v, at, GATEWAY.id) for at, v in zip(SLOTS, LATENCY, strict=True)]
    samples += [sample(80.0, at, API.id) for at in SLOTS]
    marks = [ObservationMark(s.component_id, s.observed_at, s.id, None) for s in samples]
    return ObservationIndex(samples, marks)


INDEX = observations()


def passes(
    chunks: Sequence[Sequence[datetime]], rules: Sequence[HealthRule] = RULES
) -> list[EvaluationPass]:
    """Successive passes, each fed the previous one's states, as the worker does."""
    tracks: dict[tuple[uuid.UUID, str], RuleTrack] = {}
    components: dict[uuid.UUID, Standing] = {}
    platform: Standing | None = None
    results = []
    for chunk in chunks:
        result = evaluate(
            EvaluationPlan(TOPOLOGY, rules, chunk, tracks, components, platform, INDEX)
        )
        tracks |= {(s.component_id, s.rule.key): s.track for s in result.rules}
        components |= {s.component_id: Standing(s.state, s.since) for s in result.components}
        if result.platform is not None:
            platform = Standing(result.platform.state, result.platform.since)
        results.append(result)
    return results


def history(results: Sequence[EvaluationPass]) -> list[tuple[str, datetime, HealthState]]:
    recorded: list[RecordedEvaluation] = [r for result in results for r in result.recorded]
    return [(r.rule.key, r.evaluated_at, r.state) for r in recorded]


def test_state_history_does_not_depend_on_the_worker_cadence() -> None:
    # A first one-slot pass starts every rule; the rest is evaluated in 59, 9 or 1 passes.
    start, rest = [SLOTS[:1]], SLOTS[1:]
    slot_by_slot = passes(start + [[s] for s in rest])
    by_seven = passes(start + [rest[i : i + 7] for i in range(0, len(rest), 7)])
    at_once = passes([*start, rest])

    assert history(slot_by_slot) == history(by_seven) == history(at_once)
    finals = {_platform(run) for run in (slot_by_slot, by_seven, at_once)}
    assert len(finals) == 1


def _platform(results: Sequence[EvaluationPass]) -> tuple[HealthState, datetime]:
    final = results[-1].platform
    assert final is not None
    return final.state, final.since


def test_degradation_and_recovery_follow_the_rule_and_the_platform() -> None:
    results = passes([[s] for s in SLOTS])
    changes = [
        (t.subject, t.current) for r in results for t in r.transitions if t.scope is Scope.RULE
    ]

    assert [c for s, c in changes if s == "gw/R-LAT-001"] == [H, W, C, H]
    platform = [t.current for r in results for t in r.transitions if t.scope is Scope.PLATFORM]
    assert platform == [U, H, W, C, H]


def test_rules_without_history_start_at_the_newest_slot() -> None:
    (result,) = passes([SLOTS[:10]])

    assert {r.evaluated_at for r in result.recorded} == {SLOTS[9]}
    assert {s.track.progress.state for s in result.rules} == {U}


def test_evaluations_are_recorded_on_change_and_once_a_minute() -> None:
    results = passes([SLOTS[:1], SLOTS[1:]])
    api_absence = [
        r.evaluated_at
        for res in results
        for r in res.recorded
        if r.component_id == API.id and r.rule.key == "R-TEL-001"
    ]

    # First evaluation (Unknown), Healthy at the second (clear_after 2), then every 60 s.
    assert api_absence[:4] == [SLOTS[0], SLOTS[1], SLOTS[13], SLOTS[25]]


def test_impact_and_reason_come_with_the_component_snapshot() -> None:
    results = passes([[s] for s in SLOTS[:30]])
    by_component = {c.component_id: c for c in results[-1].components}

    assert by_component[GATEWAY.id].state is C
    assert by_component[API.id].impacted_by == (GATEWAY.id,)
    assert by_component[API.id].state is H
    assert by_component[GATEWAY.id].reason is not None


@pytest.mark.parametrize(
    ("seen", "expected", "skipped"),
    [
        (None, [SLOTS[47]], 0),
        (SLOTS[40], SLOTS[41:48], 0),
        (SLOTS[47], [], 0),
        (SLOTS[0], SLOTS[48 - 12 : 48], 35),
    ],
)
def test_slots_to_evaluate_resume_after_the_oldest_rule_within_the_bound(
    seen: datetime | None, expected: list[datetime], skipped: int
) -> None:
    pairs = applicable_pairs([GATEWAY], RULES[:1])
    prior = {} if seen is None else {(GATEWAY.id, RULES[0].key): _track(seen)}

    planned = slots_to_evaluate(pairs, prior, SLOTS[47], max_slots=12)

    assert (planned.slots, planned.skipped) == (expected, skipped)


def test_skipped_slots_break_the_streak_in_progress() -> None:
    # Two breaching slots before a gap and one after: not three consecutive evaluations.
    rule = RULES[0]
    before = RuleTrack(RuleProgress(H, T0, C, 2), SLOTS[0], SLOTS[0], 1, 1, C)
    plan = EvaluationPlan(
        TOPOLOGY, [rule], [SLOTS[30]], {(GATEWAY.id, rule.key): before}, {}, None, INDEX
    )

    (snapshot,) = [s for s in evaluate(plan).rules if s.component_id == GATEWAY.id]

    assert (snapshot.track.progress.state, snapshot.track.progress.streak) == (H, 1)


def _track(at: datetime) -> RuleTrack:
    return RuleTrack(RuleProgress(H, at), at, at, 1, 1, H)
