from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class WallClock:
    """Real UTC time, for the monitor's own liveness and audit `occurred_at`.

    Business timestamps use the platform clock instead (D-13, ADR 0002).
    """

    def now(self) -> datetime:
        return datetime.now(UTC)
