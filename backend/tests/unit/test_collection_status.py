import uuid
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import pytest

from app.core.observation import ObservationSource
from app.ingestion.domain.collection import (
    CollectionOutcome,
    CollectionRun,
    CollectionStatus,
)
from app.monitor.domain import CollectionState, assess_collection, worst_collection_state

NOW = datetime(2026, 1, 1, tzinfo=UTC)
INTERVAL_S = 5.0


@pytest.mark.parametrize(
    ("outcome", "status"),
    [
        (CollectionOutcome(sample_count=10), CollectionStatus.OK),
        (CollectionOutcome(sample_count=0), CollectionStatus.OK),
        (CollectionOutcome(sample_count=0, duplicate_count=10), CollectionStatus.OK),
        (
            CollectionOutcome(sample_count=9, rejections={"UNIT_MISMATCH": 1}),
            CollectionStatus.PARTIAL,
        ),
        (
            CollectionOutcome(sample_count=9, error_code="BROKER_SLOW", error_message="slow"),
            CollectionStatus.PARTIAL,
        ),
        (CollectionOutcome.failed("CONNECTOR_ERROR", "boom"), CollectionStatus.FAILED),
        (CollectionOutcome(rejections={"UNIT_MISMATCH": 39}), CollectionStatus.FAILED),
        (
            CollectionOutcome(duplicate_count=1, rejections={"UNIT_MISMATCH": 1}),
            CollectionStatus.PARTIAL,
        ),
    ],
)
def test_outcome_status(outcome: CollectionOutcome, status: CollectionStatus) -> None:
    assert outcome.status is status


def test_rejected_count_sums_every_code() -> None:
    outcome = CollectionOutcome(rejections={"UNIT_MISMATCH": 2, "UNKNOWN_METRIC": 3})

    assert outcome.rejected_count == 5


def run(status: CollectionStatus, age_s: float, *, rejected: int = 0) -> CollectionRun:
    started = NOW - timedelta(seconds=age_s)
    return CollectionRun(
        id=uuid.uuid4(),
        connector_key="simulation",
        source=ObservationSource.SIMULATION,
        started_at=started,
        finished_at=started,
        status=status,
        sample_count=0,
        log_count=0,
        rejected_count=rejected,
        duplicate_count=0,
        rejections=MappingProxyType({}),
        watermark=None,
        error_code="CONNECTOR_ERROR" if status is CollectionStatus.FAILED else None,
        error_message=None,
    )


@pytest.mark.parametrize(
    ("last", "state"),
    [
        (None, CollectionState.NOT_STARTED),
        (run(CollectionStatus.OK, 1), CollectionState.OK),
        (run(CollectionStatus.PARTIAL, 1, rejected=3), CollectionState.DEGRADED),
        (run(CollectionStatus.FAILED, 1), CollectionState.FAILED),
        (run(CollectionStatus.OK, 15), CollectionState.OK),
        (run(CollectionStatus.OK, 16), CollectionState.STALLED),
        (run(CollectionStatus.FAILED, 16), CollectionState.STALLED),
    ],
)
def test_collection_assessment(last: CollectionRun | None, state: CollectionState) -> None:
    assert assess_collection(last, NOW, INTERVAL_S).state is state


def test_stalled_collection_says_how_long_it_has_been_silent() -> None:
    detail = assess_collection(run(CollectionStatus.OK, 60), NOW, INTERVAL_S).detail

    assert "60 s ago" in detail


@pytest.mark.parametrize(
    ("states", "worst"),
    [
        ([], CollectionState.NOT_STARTED),
        ([CollectionState.OK, CollectionState.DEGRADED], CollectionState.DEGRADED),
        ([CollectionState.OK, CollectionState.STALLED], CollectionState.STALLED),
        ([CollectionState.STALLED, CollectionState.FAILED], CollectionState.FAILED),
    ],
)
def test_overall_state_is_the_worst_connector_state(
    states: list[CollectionState], worst: CollectionState
) -> None:
    assert worst_collection_state(states) is worst
