import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from app.connectors.domain import CollectionResult, ObservedLog, ObservedSample
from app.core.observation import LogSeverity, Quality
from app.ingestion.domain.catalog import METRIC_CATALOG
from app.ingestion.domain.validation import (
    MAX_LOG_ATTRIBUTES_BYTES,
    MAX_LOG_MESSAGE_CHARS,
    AcceptedSample,
    IngestionPolicy,
    RejectionCode,
    ValidationContext,
    log_fingerprint,
    validate,
)

NOW = datetime(2026, 1, 1, 12, tzinfo=UTC)
COLLECTOR_ID = uuid.uuid4()
CONTEXT = ValidationContext(
    now=NOW,
    components={"collector-01": COLLECTOR_ID},
    catalog={d.metric_name: d for d in METRIC_CATALOG},
    policy=IngestionPolicy(),
)
SAMPLE = ObservedSample("collector-01", "probe_latency_ms", 42.0, "ms", Quality.GOOD, NOW)
LOG = ObservedLog("collector-01", LogSeverity.ERROR, "Read timeout", {"request_id": "a1"}, NOW)


def sample_codes(**changes: Any) -> list[RejectionCode]:
    batch = validate(CollectionResult(samples=(replace(SAMPLE, **changes),)), CONTEXT)
    return [r.code for r in batch.rejections]


def log_codes(**changes: Any) -> list[RejectionCode]:
    batch = validate(CollectionResult(logs=(replace(LOG, **changes),)), CONTEXT)
    return [r.code for r in batch.rejections]


def test_valid_sample_is_accepted_with_component_id_and_utc_time() -> None:
    paris = timezone(timedelta(hours=1))
    observed = ObservedSample(
        "collector-01", "cpu_pct", 12.5, "%", Quality.UNCERTAIN, NOW.astimezone(paris)
    )

    batch = validate(CollectionResult(samples=(observed,)), CONTEXT)

    assert batch.rejections == ()
    assert batch.samples == (
        AcceptedSample(COLLECTOR_ID, "cpu_pct", 12.5, "%", Quality.UNCERTAIN, NOW, None),
    )
    assert batch.samples[0].observed_at.tzinfo is UTC


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"component_key": "ghost-01"}, RejectionCode.UNKNOWN_COMPONENT),
        ({"metric_name": "temperature_c"}, RejectionCode.UNKNOWN_METRIC),
        ({"unit": "s"}, RejectionCode.UNIT_MISMATCH),
        ({"value": float("nan")}, RejectionCode.VALUE_NOT_FINITE),
        ({"value": float("inf")}, RejectionCode.VALUE_NOT_FINITE),
        ({"value": -1.0}, RejectionCode.METRIC_OUT_OF_RANGE),
        ({"value": 600_001.0}, RejectionCode.METRIC_OUT_OF_RANGE),
        ({"observed_at": NOW.replace(tzinfo=None)}, RejectionCode.TIMESTAMP_NOT_AWARE),
        ({"observed_at": NOW + timedelta(seconds=31)}, RejectionCode.OBSERVATION_IN_FUTURE),
        (
            {"observed_at": NOW - timedelta(minutes=10, seconds=1)},
            RejectionCode.OBSERVATION_TOO_LATE,
        ),
    ],
)
def test_invalid_sample_is_rejected_with_its_code(
    changes: dict[str, Any], code: RejectionCode
) -> None:
    assert sample_codes(**changes) == [code]


@pytest.mark.parametrize(
    "observed_at",
    [NOW + timedelta(seconds=30), NOW - timedelta(minutes=10), NOW - timedelta(minutes=9)],
)
def test_observation_inside_time_tolerances_is_accepted(observed_at: datetime) -> None:
    assert sample_codes(observed_at=observed_at) == []


@pytest.mark.parametrize("value", [0.0, 600_000.0])
def test_range_bounds_are_inclusive(value: float) -> None:
    assert sample_codes(value=value) == []


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"component_key": "ghost-01"}, RejectionCode.UNKNOWN_COMPONENT),
        ({"message": "   "}, RejectionCode.LOG_MESSAGE_INVALID),
        ({"message": "bad\x00byte"}, RejectionCode.LOG_MESSAGE_INVALID),
        ({"message": "x" * (MAX_LOG_MESSAGE_CHARS + 1)}, RejectionCode.LOG_MESSAGE_TOO_LONG),
        ({"attributes": {"ratio": float("nan")}}, RejectionCode.LOG_ATTRIBUTES_INVALID),
        ({"attributes": {"key": "nul\x00"}}, RejectionCode.LOG_ATTRIBUTES_INVALID),
        (
            {"attributes": {"blob": "x" * MAX_LOG_ATTRIBUTES_BYTES}},
            RejectionCode.LOG_ATTRIBUTES_TOO_LARGE,
        ),
        ({"observed_at": NOW + timedelta(minutes=1)}, RejectionCode.OBSERVATION_IN_FUTURE),
    ],
)
def test_invalid_log_is_rejected_with_its_code(
    changes: dict[str, Any], code: RejectionCode
) -> None:
    assert log_codes(**changes) == [code]


def test_log_at_maximum_length_is_accepted() -> None:
    assert log_codes(message="x" * MAX_LOG_MESSAGE_CHARS) == []


def test_rejections_are_counted_per_code() -> None:
    result = CollectionResult(
        samples=(
            SAMPLE,
            replace(SAMPLE, unit="s"),
            replace(SAMPLE, unit="s", metric_name="cpu_pct"),
            replace(SAMPLE, value=-5.0),
        ),
        logs=(replace(LOG, component_key="ghost-01"),),
    )

    batch = validate(result, CONTEXT)

    assert len(batch.samples) == 1
    assert batch.rejection_counts() == {
        "METRIC_OUT_OF_RANGE": 1,
        "UNIT_MISMATCH": 2,
        "UNKNOWN_COMPONENT": 1,
    }


def test_fingerprint_groups_messages_that_differ_only_by_variable_parts() -> None:
    first = log_fingerprint(LogSeverity.ERROR, "Retry 3 failed for request 0a1b2c3d4e")
    second = log_fingerprint(LogSeverity.ERROR, "Retry 7 failed for request ffee001122")

    assert first == second
    assert first != log_fingerprint(LogSeverity.WARNING, "Retry 3 failed for request 0a1b2c3d4e")
    assert first != log_fingerprint(LogSeverity.ERROR, "Retry 3 succeeded")


def test_dedup_key_distinguishes_logs_with_different_attributes() -> None:
    result = CollectionResult(logs=(LOG, replace(LOG, attributes={"request_id": "b2"}), LOG))

    keys = [log.dedup_key for log in validate(result, CONTEXT).logs]

    assert keys[0] == keys[2]
    assert keys[0] != keys[1]
