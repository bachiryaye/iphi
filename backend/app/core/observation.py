"""Observation vocabulary shared by producers (simulation, connectors) and ingestion."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum

UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
# Platform-time period of the probes (ADR 0014), the resolution of raw series and the cadence of
# rule evaluations, whatever the worker period: accelerated mode yields more slots per wall
# second, not sparser series.
SAMPLE_INTERVAL_S = 5
SAMPLE_INTERVAL = timedelta(seconds=SAMPLE_INTERVAL_S)


def tick_of(at: datetime) -> int:
    """Index of the last sample slot at or before `at`."""
    return (at - UNIX_EPOCH) // SAMPLE_INTERVAL


def tick_time(tick: int) -> datetime:
    return UNIX_EPOCH + tick * SAMPLE_INTERVAL


class ObservationSource(StrEnum):
    """Stored on every observation so synthetic data is never mistaken for real (D-17)."""

    SIMULATION = "simulation"
    MQTT = "mqtt"


class Quality(StrEnum):
    """OPC UA status semantics (rules.md S-05, D-16), declared from best to worst."""

    GOOD = "good"
    UNCERTAIN = "uncertain"
    BAD = "bad"


class LogSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _SEVERITY_ORDER.index(self)


_SEVERITY_ORDER = tuple(LogSeverity)
