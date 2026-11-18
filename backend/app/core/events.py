"""Transactional change notices; PostgreSQL delivers NOTIFY only after commit (P-06)."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.orm import Session

CHANNEL = "iphi_events"
MAX_NOTICE_BYTES = 1024


class NoticeType(StrEnum):
    PLATFORM = "platform.health_changed"
    COMPONENT = "component.health_changed"
    INCIDENT_OPENED = "incident.opened"
    INCIDENT_UPDATED = "incident.updated"
    INCIDENT_RESOLVED = "incident.resolved"
    SCENARIO = "scenario.changed"
    MONITOR = "monitor.status"
    HEARTBEAT = "heartbeat"
    SYNC = "sync"


@dataclass(frozen=True, slots=True)
class Notice:
    type: NoticeType
    id: str
    platform_time: datetime

    def __post_init__(self) -> None:
        if not 1 <= len(self.id) <= 64:
            raise ValueError("Invalid entity ID.")
        if self.platform_time.tzinfo is None or self.platform_time.utcoffset() != UTC.utcoffset(
            self.platform_time
        ):
            raise ValueError("Notice time must be UTC.")

    def encode(self) -> str:
        return json.dumps(
            {
                "type": self.type.value,
                "id": self.id,
                "platform_time": self.platform_time.astimezone(UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "environment": "simulation",
            },
            separators=(",", ":"),
        )

    @classmethod
    def decode(cls, value: str) -> Notice:
        if len(value.encode()) > MAX_NOTICE_BYTES:
            raise ValueError("Oversized notice.")
        data = json.loads(value)
        if not isinstance(data, dict) or set(data) != {
            "type",
            "id",
            "platform_time",
            "environment",
        }:
            raise ValueError("Invalid notice fields.")
        if data["environment"] != "simulation":
            raise ValueError("Not a simulation notice.")
        if not isinstance(data["id"], str) or not 1 <= len(data["id"]) <= 64:
            raise ValueError("Invalid entity ID.")
        if not isinstance(data["type"], str) or not isinstance(data["platform_time"], str):
            raise ValueError("Invalid notice types.")
        at = datetime.fromisoformat(data["platform_time"])
        if at.tzinfo is None or at.utcoffset() != UTC.utcoffset(at):
            raise ValueError("Notice time must be UTC.")
        return cls(NoticeType(data["type"]), data["id"], at)


def notify(session: Session, notice: Notice) -> None:
    session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {
            "channel": CHANNEL,
            "payload": notice.encode(),
        },
    )
