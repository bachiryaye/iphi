from dataclasses import dataclass
from datetime import datetime


@dataclass
class FixedClock:
    current: datetime

    def now(self) -> datetime:
        return self.current


class NoScenarios:
    """Scenario lifecycle for worker tests that do not exercise the simulation."""

    def complete_expired_runs(self) -> list[object]:
        return []
