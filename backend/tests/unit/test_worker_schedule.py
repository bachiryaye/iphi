import pytest

from app.worker import next_deadline


@pytest.mark.parametrize(
    ("previous", "now", "expected"),
    [
        (100.0, 100.2, 105.0),
        (100.0, 104.9, 105.0),
        (100.0, 105.0, 105.0),
        (100.0, 160.0, 160.0),
    ],
)
def test_next_deadline_keeps_cadence_and_skips_missed_slots(
    previous: float, now: float, expected: float
) -> None:
    assert next_deadline(previous, 5.0, now) == expected
