"""Metric catalog (rules.md D-15): every accepted metric has one canonical unit and a range.

The catalog is code-defined and seeded into `metric_definition` at bootstrap, so the API and
the validator read the same persisted definitions.
"""

from dataclasses import dataclass
from enum import StrEnum


class MetricKind(StrEnum):
    GAUGE = "gauge"
    COUNTER = "counter"
    RATIO = "ratio"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_name: str
    unit: str
    description: str
    min_value: float
    max_value: float
    kind: MetricKind

    def __post_init__(self) -> None:
        if self.min_value >= self.max_value:
            raise ValueError(f"{self.metric_name}: min_value must be below max_value")

    def admits(self, value: float) -> bool:
        return self.min_value <= value <= self.max_value


ONE_YEAR_S = 365 * 24 * 3600

METRIC_CATALOG: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        "up", "bool", "Active probe result: 1 when the component answered, 0 otherwise.",
        0, 1, MetricKind.GAUGE,
    ),
    MetricDefinition(
        "probe_latency_ms", "ms", "Round-trip time of the active probe.",
        0, 600_000, MetricKind.GAUGE,
    ),
    MetricDefinition(
        "data_age_s", "s", "Age of the newest process data the component holds.",
        0, ONE_YEAR_S, MetricKind.GAUGE,
    ),
    MetricDefinition(
        "error_count", "count", "Errors during the sample interval (a delta, not a running total).",
        0, 100_000, MetricKind.COUNTER,
    ),
    MetricDefinition(
        "cpu_pct", "%", "Processor utilisation.", 0, 100, MetricKind.GAUGE,
    ),
    MetricDefinition(
        "mem_pct", "%", "Memory utilisation.", 0, 100, MetricKind.GAUGE,
    ),
    MetricDefinition(
        "queue_depth", "count", "Messages waiting in the component's buffer.",
        0, 10_000_000, MetricKind.GAUGE,
    ),
)  # fmt: skip
