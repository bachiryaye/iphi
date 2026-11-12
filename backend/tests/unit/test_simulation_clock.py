from datetime import UTC, datetime, timedelta

import pytest

from app.simulation.domain.clock import (
    SAMPLE_INTERVAL_S,
    ClockMode,
    ClockState,
    first_tick_at_or_after,
    tick_of,
    tick_time,
)
from app.simulation.domain.errors import ClockNotManualError, ClockSpeedError

WALL = datetime(2026, 11, 12, 10, 0, tzinfo=UTC)
SEED = 42


def later(seconds: float) -> datetime:
    return WALL + timedelta(seconds=seconds)


def test_realtime_clock_follows_wall_time_from_its_anchor() -> None:
    clock = ClockState.initial(SEED, WALL)

    assert clock.platform_time(later(30)) == later(30)


def test_accelerated_clock_multiplies_elapsed_wall_time() -> None:
    clock = ClockState.initial(SEED, WALL).switched(ClockMode.ACCELERATED, 10.0, WALL)

    assert clock.platform_time(later(6)) == later(60)


def test_manual_clock_ignores_wall_time() -> None:
    clock = ClockState.initial(SEED, WALL).switched(ClockMode.MANUAL, 1.0, WALL)

    assert clock.platform_time(later(3600)) == WALL


def test_mode_switch_keeps_platform_time_continuous() -> None:
    accelerated = ClockState.initial(SEED, WALL).switched(ClockMode.ACCELERATED, 10.0, WALL)
    before = accelerated.platform_time(later(6))

    realtime = accelerated.switched(ClockMode.REALTIME, 1.0, later(6))

    assert realtime.platform_time(later(6)) == before
    assert realtime.platform_time(later(16)) == before + timedelta(seconds=10)


def test_advance_moves_a_manual_clock() -> None:
    manual = ClockState.initial(SEED, WALL).switched(ClockMode.MANUAL, 1.0, WALL)

    assert manual.advanced(30, later(1)).platform_time(later(2)) == later(30)


@pytest.mark.parametrize("mode", [ClockMode.REALTIME, ClockMode.ACCELERATED])
def test_advance_is_refused_outside_manual_mode(mode: ClockMode) -> None:
    speed = 10.0 if mode is ClockMode.ACCELERATED else 1.0
    clock = ClockState.initial(SEED, WALL).switched(mode, speed, WALL)

    with pytest.raises(ClockNotManualError):
        clock.advanced(30, WALL)


def test_reset_never_moves_platform_time_backwards() -> None:
    ahead = ClockState.initial(SEED, WALL).switched(ClockMode.ACCELERATED, 60.0, WALL)
    platform_before = ahead.platform_time(later(60))

    reset = ahead.reset(7, later(60))

    assert reset.mode is ClockMode.REALTIME
    assert reset.seed == 7
    assert reset.platform_time(later(60)) == platform_before


def test_reset_of_a_clock_behind_wall_time_restarts_at_wall_time() -> None:
    manual = ClockState.initial(SEED, WALL).switched(ClockMode.MANUAL, 1.0, WALL)

    assert manual.reset(SEED, later(600)).platform_time(later(600)) == later(600)


def test_wall_clock_stepping_back_does_not_move_platform_time_back() -> None:
    clock = ClockState.initial(SEED, WALL)

    assert clock.platform_time(WALL - timedelta(seconds=5)) == WALL


@pytest.mark.parametrize(
    ("mode", "speed"),
    [
        (ClockMode.ACCELERATED, 1.0),
        (ClockMode.ACCELERATED, 61.0),
        (ClockMode.REALTIME, 2.0),
        (ClockMode.MANUAL, 10.0),
    ],
)
def test_speed_outside_its_mode_range_is_rejected(mode: ClockMode, speed: float) -> None:
    with pytest.raises(ClockSpeedError):
        ClockState(mode, speed, WALL, WALL, SEED)


def test_naive_anchor_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ClockState(ClockMode.REALTIME, 1.0, WALL.replace(tzinfo=None), WALL, SEED)


def test_ticks_are_aligned_sample_slots() -> None:
    tick = tick_of(WALL + timedelta(seconds=7))

    assert tick_time(tick) == WALL + timedelta(seconds=5)
    assert tick_time(tick + 1) - tick_time(tick) == timedelta(seconds=SAMPLE_INTERVAL_S)
    assert tick_of(tick_time(tick)) == tick


def test_first_tick_of_an_unaligned_start_is_the_next_slot() -> None:
    aligned = tick_time(tick_of(WALL))

    assert first_tick_at_or_after(aligned) == tick_of(aligned)
    assert tick_time(first_tick_at_or_after(aligned + timedelta(seconds=3))) == aligned + timedelta(
        seconds=SAMPLE_INTERVAL_S
    )
