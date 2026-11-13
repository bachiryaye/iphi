"""Builders of health rules and observations for domain tests."""

import itertools
import uuid
from datetime import UTC, datetime, timedelta

from app.core.observation import Quality
from app.health.domain.rules import (
    Aggregation,
    FailureClass,
    HealthRule,
    Level,
    Measure,
    Operator,
    RuleDefinition,
    RuleType,
    TargetSelector,
)
from app.ingestion.domain.observations import StoredSample

T0 = datetime(2026, 1, 1, tzinfo=UTC)
SLOT = timedelta(seconds=5)
_ids = itertools.count(1)


def latency_rule(
    raise_after: int = 3, clear_after: int = 3, window_seconds: int = 60, min_samples: int = 1
) -> HealthRule:
    """R-LAT-001 as configured: p95 > 250 warning (clear 200), > 1000 critical (clear 800)."""
    definition = RuleDefinition(
        rule_type=RuleType.THRESHOLD,
        failure_class=FailureClass.LATENCY,
        targets=TargetSelector(),
        measure=Measure(
            "probe_latency_ms",
            Aggregation.P95,
            Operator.GT,
            Level(250, 200),
            Level(1000, 800),
        ),
        window_seconds=window_seconds,
        raise_after=raise_after,
        clear_after=clear_after,
        min_samples=min_samples,
        rationale="Slow probes.",
        recommendation="Check the path.",
    )
    return HealthRule(uuid.uuid4(), "R-LAT-001", 1, definition, "ms", T0)


def availability_rule() -> HealthRule:
    definition = RuleDefinition(
        rule_type=RuleType.THRESHOLD,
        failure_class=FailureClass.AVAILABILITY,
        targets=TargetSelector(),
        measure=Measure("up", Aggregation.LAST, Operator.LT, None, Level(1, 1)),
        window_seconds=10,
        raise_after=2,
        clear_after=3,
        min_samples=1,
        rationale="No answer.",
        recommendation="Check the process.",
    )
    return HealthRule(uuid.uuid4(), "R-AVAIL-001", 1, definition, "bool", T0)


def absence_rule() -> HealthRule:
    definition = RuleDefinition(
        rule_type=RuleType.ABSENCE,
        failure_class=FailureClass.TELEMETRY_LOSS,
        targets=TargetSelector(),
        measure=None,
        window_seconds=15,
        raise_after=1,
        clear_after=2,
        min_samples=1,
        rationale="Blind.",
        recommendation="Check the connector.",
    )
    return HealthRule(uuid.uuid4(), "R-TEL-001", 1, definition, None, T0)


def sample(
    value: float,
    at: datetime = T0,
    component_id: uuid.UUID | None = None,
    metric: str = "probe_latency_ms",
    quality: Quality = Quality.GOOD,
) -> StoredSample:
    return StoredSample(next(_ids), component_id or uuid.uuid4(), metric, value, quality, at)
