"""Debounced rule state (architecture §05.3, rules.md D-09, S-03 ISA-18.2 on-/off-delay).

A rule moves to a more severe state after `raise_after` consecutive evaluations calling for it,
and back after `clear_after` consecutive evaluations within the clear thresholds. Severity
follows HealthState: losing evidence (Unknown) is a degradation from Warning or Healthy and an
improvement from Critical, so a confirmed failure is held for `clear_after` evaluations before
it turns Unknown.
"""

from dataclasses import dataclass
from datetime import datetime

from app.health.domain.evaluation import Measurement, held_level
from app.health.domain.rules import RuleDefinition
from app.health.domain.states import HealthState


@dataclass(frozen=True, slots=True)
class RuleProgress:
    """`pending` is the state a running streak would reach; `streak` its consecutive count."""

    state: HealthState
    since: datetime
    pending: HealthState | None = None
    streak: int = 0

    def __post_init__(self) -> None:
        if (self.pending is None) != (self.streak == 0) or self.pending is self.state:
            raise ValueError("a streak needs a pending state other than the current one")

    @classmethod
    def initial(cls, at: datetime) -> RuleProgress:
        """No evaluation yet: Unknown, never Healthy (D-02)."""
        return cls(HealthState.UNKNOWN, at)


def target_state(
    definition: RuleDefinition, measurement: Measurement, current: HealthState
) -> HealthState:
    """State this evaluation calls for, before debouncing."""
    raw, value = measurement.raw_state, measurement.observed_value
    if definition.measure is None or value is None or current is HealthState.UNKNOWN:
        return raw
    if raw.is_worse_than(current):
        return raw
    held = held_level(definition.measure, value)
    return held if current.is_worse_than(held) else current


def required_streak(definition: RuleDefinition, progress: RuleProgress) -> int | None:
    """Consecutive evaluations the pending transition needs; None without a pending one."""
    if progress.pending is None:
        return None
    raising = progress.pending.is_worse_than(progress.state)
    return definition.raise_after if raising else definition.clear_after


def advance(
    definition: RuleDefinition, progress: RuleProgress, target: HealthState, at: datetime
) -> RuleProgress:
    if target is progress.state:
        return RuleProgress(progress.state, progress.since)
    raising = target.is_worse_than(progress.state)
    pending, streak = target, 1
    if progress.pending is not None and progress.pending.is_worse_than(progress.state) == raising:
        # The streak may mix targets in one direction; it reaches the mildest of them, so every
        # evaluation of the streak called for at least that much change.
        mildest = min if raising else max
        pending = mildest(progress.pending, target, key=lambda s: s.severity)
        streak = progress.streak + 1
    required = definition.raise_after if raising else definition.clear_after
    if streak >= required:
        return RuleProgress(pending, at)
    return RuleProgress(progress.state, progress.since, pending, streak)
