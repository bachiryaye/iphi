"""Health states (rules.md D-01) and their severity order (ADR 0004)."""

from enum import StrEnum


class HealthState(StrEnum):
    """Declared from least to most severe: Critical > Unknown > Warning > Healthy.

    Unknown ranks above Warning so that missing evidence is never hidden behind a known
    degradation, and below Critical so that a confirmed failure is never hidden behind it.
    """

    HEALTHY = "healthy"
    WARNING = "warning"
    UNKNOWN = "unknown"
    CRITICAL = "critical"

    @property
    def severity(self) -> int:
        return _ORDER.index(self)

    def is_worse_than(self, other: HealthState) -> bool:
        return self.severity > other.severity


_ORDER = tuple(HealthState)
