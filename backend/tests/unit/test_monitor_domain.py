from datetime import UTC, datetime, timedelta

import pytest

from app.monitor.domain import (
    CheckName,
    CheckStatus,
    Heartbeat,
    ProcessStatus,
    ReadinessCheck,
    ReadinessReport,
    assess_migrations,
    assess_worker,
)

NOW = datetime(2026, 11, 12, 10, 42, 7, tzinfo=UTC)
INTERVAL_S = 5.0


def heartbeat(age_s: float, status: ProcessStatus = ProcessStatus.RUNNING) -> Heartbeat:
    return Heartbeat("worker", NOW - timedelta(seconds=age_s), 12, 0, status)


def test_missing_heartbeat_fails_readiness() -> None:
    check = assess_worker(None, NOW, INTERVAL_S)

    assert check.status is CheckStatus.FAILED
    assert check.observed_at is None


@pytest.mark.parametrize(
    ("age_s", "expected"),
    [
        (0.0, CheckStatus.OK),
        (14.9, CheckStatus.OK),
        (15.0, CheckStatus.OK),
        (15.1, CheckStatus.FAILED),
        (600.0, CheckStatus.FAILED),
    ],
)
def test_worker_is_stalled_after_three_missed_cycles(age_s: float, expected: CheckStatus) -> None:
    assert assess_worker(heartbeat(age_s), NOW, INTERVAL_S).status is expected


def test_stalled_worker_reports_age_and_expected_cadence() -> None:
    check = assess_worker(heartbeat(80), NOW, INTERVAL_S)

    assert check.detail == "Worker stalled: last cycle 80 s ago, expected every 5 s."
    assert check.observed_at == NOW - timedelta(seconds=80)


def test_stopped_worker_fails_even_with_recent_heartbeat() -> None:
    check = assess_worker(heartbeat(1, ProcessStatus.STOPPED), NOW, INTERVAL_S)

    assert check.status is CheckStatus.FAILED
    assert check.detail == "Worker stopped."


@pytest.mark.parametrize(
    ("current", "expected"),
    [("0001", CheckStatus.OK), ("0000", CheckStatus.FAILED), (None, CheckStatus.FAILED)],
)
def test_migrations_must_match_code_head(current: str | None, expected: CheckStatus) -> None:
    assert assess_migrations(current, "0001").status is expected


def test_disabled_check_does_not_block_readiness() -> None:
    report = ReadinessReport(
        NOW,
        INTERVAL_S,
        (
            ReadinessCheck(CheckName.DATABASE, CheckStatus.OK, ""),
            ReadinessCheck(CheckName.AI_PROVIDER, CheckStatus.DISABLED, ""),
        ),
    )

    assert report.ready


def test_any_failed_check_blocks_readiness() -> None:
    report = ReadinessReport(
        NOW,
        INTERVAL_S,
        (
            ReadinessCheck(CheckName.DATABASE, CheckStatus.OK, ""),
            ReadinessCheck(CheckName.WORKER, CheckStatus.FAILED, ""),
        ),
    )

    assert not report.ready


def test_heartbeat_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Heartbeat("worker", datetime(2026, 11, 12), 0, 0, ProcessStatus.RUNNING)  # noqa: DTZ001


def test_heartbeat_rejects_negative_durations() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        Heartbeat("worker", NOW, -1, 0, ProcessStatus.RUNNING)
