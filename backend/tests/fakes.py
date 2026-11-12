from dataclasses import dataclass
from datetime import datetime


@dataclass
class FixedClock:
    current: datetime

    def now(self) -> datetime:
        return self.current
