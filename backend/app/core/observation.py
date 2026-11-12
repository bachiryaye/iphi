"""Observation vocabulary shared by producers (simulation, connectors) and ingestion."""

from datetime import UTC, datetime
from enum import StrEnum

UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
# Platform-time period of the simulated probes (ADR 0014), also the resolution of raw series.
SAMPLE_INTERVAL_S = 5


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
