from collections.abc import Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.health.domain.evaluation import Evidence, Measurement, raw_level
from app.health.domain.hysteresis import RuleProgress, advance, required_streak, target_state
from app.health.domain.rules import HealthRule
from app.health.domain.states import HealthState
from tests.health_rules import SLOT, T0, latency_rule

H, W, C, U = HealthState.HEALTHY, HealthState.WARNING, HealthState.CRITICAL, HealthState.UNKNOWN
RULE = latency_rule(raise_after=3, clear_after=3)


def measured(value: float | None, rule: HealthRule = RULE) -> Measurement:
    if value is None:
        return Measurement(U, None, 0, Evidence(), "no samples")
    assert rule.definition.measure is not None
    return Measurement(raw_level(rule.definition.measure, value), value, 1, Evidence(), "")


def run(values: Sequence[float | None], start: HealthState = H) -> list[HealthState]:
    """Debounced state after each evaluation of the values, one per sample slot."""
    progress = RuleProgress(start, T0)
    states = []
    for i, value in enumerate(values, start=1):
        at = T0 + i * SLOT
        target = target_state(RULE.definition, measured(value), progress.state)
        progress = advance(RULE.definition, progress, target, at)
        states.append(progress.state)
    return states


def test_raise_requires_raise_after_consecutive_breaches() -> None:
    assert run([300, 300, 300]) == [H, H, W]


def test_interrupted_streak_starts_again() -> None:
    assert run([300, 300, 100, 300, 300]) == [H, H, H, H, H]


def test_streak_through_both_levels_reaches_the_mildest_of_them() -> None:
    # The first streak holds one Warning and two Critical: it reaches Warning only, and
    # Critical then needs a streak of its own.
    assert run([300] + [1200] * 5) == [H, H, W, W, W, C]


def test_clear_requires_values_within_the_clear_threshold() -> None:
    # 220 ms is below the warning threshold (250) but above its clear threshold (200).
    assert run([220] * 6, start=W) == [W] * 6
    assert run([150] * 3, start=W) == [W, W, H]


def test_critical_drops_to_the_level_the_value_still_holds() -> None:
    assert run([500] * 3, start=C) == [C, C, W]
    assert run([100] * 3, start=C) == [C, C, H]


def test_missing_evidence_turns_healthy_to_unknown_after_raise_after() -> None:
    assert run([None] * 3) == [H, H, U]


def test_confirmed_failure_is_held_for_clear_after_before_unknown() -> None:
    assert run([None] * 3, start=C) == [C, C, U]


def test_unknown_needs_clear_after_healthy_evaluations_to_become_healthy() -> None:
    assert run([100, 100, 100], start=U) == [U, U, H]


def test_unknown_reaches_critical_after_raise_after() -> None:
    assert run([1200] * 3, start=U) == [U, U, C]


def test_required_streak_reports_the_pending_transition() -> None:
    progress = RuleProgress(H, T0)
    progress = advance(RULE.definition, progress, W, T0 + SLOT)

    assert (progress.pending, progress.streak, required_streak(RULE.definition, progress)) == (
        W,
        1,
        3,
    )
    assert required_streak(RULE.definition, RuleProgress(H, T0)) is None


def test_state_change_moves_since_to_the_evaluation_time() -> None:
    progress = RuleProgress(H, T0)
    for i in range(1, 4):
        progress = advance(RULE.definition, progress, W, T0 + i * SLOT)

    assert (progress.state, progress.since) == (W, T0 + 3 * SLOT)


@pytest.mark.parametrize("pending", [None, H])
def test_progress_rejects_inconsistent_streaks(pending: HealthState | None) -> None:
    with pytest.raises(ValueError, match="pending"):
        RuleProgress(H, T0, pending, 0 if pending else 2)


# Values strictly inside each hysteresis band: below the raise threshold, not below the clear.
WARNING_BAND = st.floats(min_value=200, max_value=250)
CRITICAL_BAND = st.floats(min_value=800, max_value=1000)


@given(st.lists(WARNING_BAND, min_size=1, max_size=200))
def test_signal_oscillating_in_the_warning_band_never_changes_the_state(
    values: list[float],
) -> None:
    assert set(run(values, start=W)) == {W}
    assert set(run(values, start=H)) == {H}


@given(st.lists(CRITICAL_BAND, min_size=1, max_size=200))
def test_signal_oscillating_in_the_critical_band_never_changes_the_state(
    values: list[float],
) -> None:
    assert set(run(values, start=C)) == {C}
    assert set(run(values, start=W)) == {W}


@given(
    st.lists(
        st.tuples(st.integers(1, RULE.definition.raise_after - 1), st.integers(1, 5)),
        min_size=1,
        max_size=50,
    )
)
def test_breaches_shorter_than_raise_after_never_raise(runs: list[tuple[int, int]]) -> None:
    values: list[float] = []
    for breaches, normal in runs:
        values += [1500.0] * breaches + [50.0] * normal
    assert set(run(values)) == {H}


@given(st.lists(st.one_of(st.none(), st.floats(0, 5000)), min_size=1, max_size=200))
def test_unknown_becomes_healthy_only_after_clear_after_evaluations_with_healthy_evidence(
    values: list[float | None],
) -> None:
    # Leaving Unknown there is no known level, hence no deadband: the raise thresholds decide.
    states = run(values, start=U)
    clear_after = RULE.definition.clear_after
    for i, state in enumerate(states):
        previous = states[i - 1] if i else U
        if state is H and previous is U:
            window = values[i - clear_after + 1 : i + 1]
            assert len(window) == clear_after
            assert all(v is not None and v <= 250 for v in window)


@given(st.lists(st.one_of(st.none(), st.floats(0, 5000)), max_size=200))
def test_every_change_completes_a_streak_of_the_required_length(
    values: list[float | None],
) -> None:
    progress = RuleProgress(H, T0)
    for i, value in enumerate(values, start=1):
        target = target_state(RULE.definition, measured(value), progress.state)
        moved = advance(RULE.definition, progress, target, T0 + i * SLOT)
        if moved.state is not progress.state:
            raising = moved.state.is_worse_than(progress.state)
            required = RULE.definition.raise_after if raising else RULE.definition.clear_after
            assert progress.streak + 1 == required
        progress = moved
