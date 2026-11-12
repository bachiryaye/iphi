import uuid
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.ingestion.domain.series import (
    MAX_POINTS,
    Gap,
    InvalidTimeWindowError,
    SeriesQuery,
    TimeWindow,
    find_gaps,
)

START = datetime(2026, 1, 1, tzinfo=UTC)
HOUR = TimeWindow(START, START + timedelta(hours=1))
END = HOUR.end


def at(seconds: float) -> datetime:
    return START + timedelta(seconds=seconds)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (START, START),
        (START + timedelta(seconds=1), START),
        (START, START + timedelta(days=7, seconds=1)),
        (START.replace(tzinfo=None), START + timedelta(hours=1)),
    ],
)
def test_invalid_window_is_refused(start: datetime, end: datetime) -> None:
    with pytest.raises(InvalidTimeWindowError):
        TimeWindow(start, end)


def test_seven_day_window_is_accepted() -> None:
    assert TimeWindow(START, START + timedelta(days=7)).duration == timedelta(days=7)


@pytest.mark.parametrize("max_points", [0, MAX_POINTS + 1])
def test_max_points_is_bounded(max_points: int) -> None:
    with pytest.raises(InvalidTimeWindowError):
        SeriesQuery(uuid.uuid4(), "up", HOUR, max_points)


@pytest.mark.parametrize(
    ("max_points", "bucket_s"), [(720, 5), (100, 36), (7, 515), (2000, 2), (5000 // 3, 3)]
)
def test_bucket_keeps_the_window_within_max_points(max_points: int, bucket_s: int) -> None:
    query = SeriesQuery(uuid.uuid4(), "up", HOUR, max_points)

    assert query.bucket_seconds() == bucket_s


@given(
    window_s=st.integers(min_value=1, max_value=7 * 24 * 3600),
    max_points=st.integers(min_value=1, max_value=MAX_POINTS),
)
def test_bucket_count_never_exceeds_max_points(window_s: int, max_points: int) -> None:
    query = SeriesQuery(uuid.uuid4(), "up", TimeWindow(START, at(window_s)), max_points)

    buckets = -(-window_s // query.bucket_seconds())

    assert buckets <= max_points


def test_regular_samples_have_no_gap() -> None:
    times = [at(s) for s in range(0, 3600, 5)]

    assert find_gaps(times, HOUR, 5, END) == ()


def test_window_without_data_is_one_gap() -> None:
    assert find_gaps([], HOUR, 5, END) == (Gap(START, END),)


def test_missing_samples_form_a_gap_between_their_neighbours() -> None:
    times = [at(s) for s in (*range(0, 600, 5), *range(900, 3600, 5))]

    assert find_gaps(times, HOUR, 5, END) == (Gap(at(600), at(900)),)


def test_one_missing_sample_is_within_tolerance() -> None:
    times = [at(s) for s in range(0, 3600, 5) if s != 100]

    assert find_gaps(times, HOUR, 5, END) == ()


def test_leading_and_trailing_silence_are_gaps() -> None:
    times = [at(s) for s in range(600, 1200, 5)]

    assert find_gaps(times, HOUR, 5, END) == (Gap(START, at(600)), Gap(at(1200), END))


def test_future_part_of_the_window_is_not_a_gap() -> None:
    times = [at(s) for s in range(0, 1200, 5)]

    assert find_gaps(times, HOUR, 5, at(1200)) == ()
    assert find_gaps(times, HOUR, 5, at(1300)) == (Gap(at(1200), at(1300)),)


def test_window_entirely_in_the_future_has_no_gap() -> None:
    assert find_gaps([], HOUR, 5, START - timedelta(seconds=1)) == ()
