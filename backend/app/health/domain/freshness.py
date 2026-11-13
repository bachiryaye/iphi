"""Read-side staleness of stored health states (rules.md D-02; architecture §05, monitor).

A stored state is only as good as the worker that keeps evaluating it. When evaluations stop,
reads report Unknown instead of the last computed state, so a stopped monitor never shows a
stale Healthy.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.observation import SAMPLE_INTERVAL
from app.health.domain.engine import Standing
from app.health.domain.states import HealthState
from app.monitor.domain import STALE_AFTER_CYCLES


def evaluation_max_age(manual: bool, speed: float, cycle_interval_s: float) -> timedelta | None:
    """Platform-time age beyond which a stored state is stale, with the worker heartbeat's
    tolerance; None while the clock is manual, since platform time then only moves on demand."""
    if manual:
        return None
    # Evaluations sit on sample slots, up to one slot behind platform time.
    return timedelta(seconds=STALE_AFTER_CYCLES * cycle_interval_s * speed) + SAMPLE_INTERVAL


@dataclass(frozen=True, slots=True)
class ReadContext:
    platform_now: datetime
    max_age: timedelta | None


@dataclass(frozen=True, slots=True)
class HealthView:
    """`state` is what a reader must act on; `evaluated_state` is the last computed one."""

    state: HealthState
    evaluated_state: HealthState | None
    since: datetime | None
    evaluated_at: datetime | None
    stale_reason: str | None

    @property
    def stale(self) -> bool:
        return self.stale_reason is not None


def health_view(
    standing: Standing | None, evaluated_at: datetime | None, context: ReadContext
) -> HealthView:
    if standing is None or evaluated_at is None:
        return HealthView(HealthState.UNKNOWN, None, None, None, "Not evaluated yet.")
    age = context.platform_now - evaluated_at
    if context.max_age is not None and age > context.max_age:
        reason = (
            f"No evaluation for {age.total_seconds():.0f} s of platform time; "
            "the worker may be stopped or late."
        )
        # Unknown since the last evaluation: nothing is known about the time after it.
        return HealthView(HealthState.UNKNOWN, standing.state, evaluated_at, evaluated_at, reason)
    return HealthView(standing.state, standing.state, standing.since, evaluated_at, None)
