"""Observable signals of a simulated component and the counter-based noise source (ADR 0002)."""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType

OBSERVATION_SOURCE = "simulation"


class Metric(StrEnum):
    UP = "up"
    PROBE_LATENCY_MS = "probe_latency_ms"
    DATA_AGE_S = "data_age_s"
    ERROR_COUNT = "error_count"
    CPU_PCT = "cpu_pct"
    MEM_PCT = "mem_pct"
    QUEUE_DEPTH = "queue_depth"


# Canonical units (rules.md D-15); `up` is a 0/1 probe result.
UNITS: Mapping[Metric, str] = MappingProxyType(
    {
        Metric.UP: "bool",
        Metric.PROBE_LATENCY_MS: "ms",
        Metric.DATA_AGE_S: "s",
        Metric.ERROR_COUNT: "count",
        Metric.CPU_PCT: "%",
        Metric.MEM_PCT: "%",
        Metric.QUEUE_DEPTH: "count",
    }
)


class Quality(StrEnum):
    """OPC UA status semantics (rules.md S-05, D-16)."""

    GOOD = "good"
    UNCERTAIN = "uncertain"
    BAD = "bad"


class LogSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class LogLine:
    severity: LogSeverity
    message: str
    attributes: Mapping[str, str | int]


@dataclass(frozen=True, slots=True)
class Reading:
    """What one probe of a component returns: `up`, measured values when it answered, logs."""

    up: bool
    values: Mapping[Metric, float]
    logs: tuple[LogLine, ...]

    @classmethod
    def unanswered(cls) -> Reading:
        # A component that does not answer reports nothing but the failed probe itself.
        return cls(up=False, values=MappingProxyType({}), logs=())

    def with_value(self, metric: Metric, value: float) -> Reading:
        return replace(self, values=MappingProxyType({**self.values, metric: value}))

    def with_logs(self, logs: tuple[LogLine, ...]) -> Reading:
        return replace(self, logs=self.logs + logs)


def draw(seed: int, *parts: str | int) -> float:
    """Uniform value in [0, 1) that depends only on its inputs: no hidden generator state."""
    material = "|".join([str(seed), *(str(p) for p in parts)]).encode()
    digest = hashlib.blake2b(material, digest_size=8).digest()
    return int.from_bytes(digest) / 2**64


def jitter(value: float, relative: float, u: float) -> float:
    return value * (1 + relative * (2 * u - 1))


def lerp(start: float, end: float, progress: float) -> float:
    return start + (end - start) * progress
