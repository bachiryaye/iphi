"""Platform clock state (ADR 0002): pure arithmetic, persisted in `sim_clock` by the service."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from app.simulation.domain.errors import ClockNotManualError, ClockSpeedError

MAX_ACCELERATION = 60.0
# Simulated probes sample every component on this platform-time cadence, whatever the worker
# period: accelerated mode then yields more samples per wall second, not sparser series.
SAMPLE_INTERVAL_S = 5
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class ClockMode(StrEnum):
    REALTIME = "realtime"
    ACCELERATED = "accelerated"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class ClockState:
    """Platform time = `anchor_platform_time` + (wall - `anchor_wall_time`) * `speed`.

    Manual mode ignores the wall clock. Every transition rebases both anchors, so platform time
    never jumps backwards (reset included): runs and observations stay ordered.
    """

    mode: ClockMode
    speed: float
    anchor_platform_time: datetime
    anchor_wall_time: datetime
    seed: int

    def __post_init__(self) -> None:
        if self.anchor_platform_time.tzinfo is None or self.anchor_wall_time.tzinfo is None:
            raise ValueError("clock anchors must be timezone-aware")
        if self.mode is ClockMode.ACCELERATED:
            if not 1.0 < self.speed <= MAX_ACCELERATION:
                raise ClockSpeedError(
                    f"Accelerated speed must be above 1 and at most {MAX_ACCELERATION:g}."
                )
        elif self.speed != 1.0:
            raise ClockSpeedError(f"Speed applies to accelerated mode only, not {self.mode}.")

    @classmethod
    def initial(cls, seed: int, wall_now: datetime) -> ClockState:
        return cls(ClockMode.REALTIME, 1.0, wall_now, wall_now, seed)

    def platform_time(self, wall_now: datetime) -> datetime:
        if self.mode is ClockMode.MANUAL:
            return self.anchor_platform_time
        # A wall clock stepping backwards (NTP) must not move platform time backwards.
        elapsed = max(timedelta(0), wall_now - self.anchor_wall_time)
        return self.anchor_platform_time + elapsed * self.speed

    def switched(self, mode: ClockMode, speed: float, wall_now: datetime) -> ClockState:
        return ClockState(mode, speed, self.platform_time(wall_now), wall_now, self.seed)

    def advanced(self, seconds: int, wall_now: datetime) -> ClockState:
        if self.mode is not ClockMode.MANUAL:
            raise ClockNotManualError(f"Advancing requires manual mode; the clock is {self.mode}.")
        moved = self.anchor_platform_time + timedelta(seconds=seconds)
        return ClockState(self.mode, self.speed, moved, wall_now, self.seed)

    def reset(self, seed: int, wall_now: datetime) -> ClockState:
        start = max(wall_now, self.platform_time(wall_now))
        return ClockState(ClockMode.REALTIME, 1.0, start, wall_now, seed)


def tick_of(at: datetime) -> int:
    """Index of the last sample slot at or before `at`."""
    return (at - _EPOCH) // timedelta(seconds=SAMPLE_INTERVAL_S)


def tick_time(tick: int) -> datetime:
    return _EPOCH + timedelta(seconds=tick * SAMPLE_INTERVAL_S)


def first_tick_at_or_after(at: datetime) -> int:
    """First sample slot a run starting at `at` covers."""
    tick = tick_of(at)
    return tick if tick_time(tick) == at else tick + 1
