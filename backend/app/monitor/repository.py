from datetime import datetime

from sqlalchemy import CheckConstraint, Integer, String, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base
from app.monitor.domain import Heartbeat, ProcessStatus


class MonitorHeartbeatRecord(Base):
    __tablename__ = "monitor_heartbeat"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'stopped')", name="status"),
        CheckConstraint("last_cycle_duration_ms >= 0", name="duration_non_negative"),
        CheckConstraint("cycle_lag_ms >= 0", name="lag_non_negative"),
    )

    process: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_cycle_at: Mapped[datetime]
    last_cycle_duration_ms: Mapped[int] = mapped_column(Integer)
    cycle_lag_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))


class HeartbeatRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, heartbeat: Heartbeat) -> None:
        values = {
            "process": heartbeat.process,
            "last_cycle_at": heartbeat.last_cycle_at,
            "last_cycle_duration_ms": heartbeat.last_cycle_duration_ms,
            "cycle_lag_ms": heartbeat.cycle_lag_ms,
            "status": heartbeat.status.value,
        }
        statement = insert(MonitorHeartbeatRecord).values(values)
        self._session.execute(
            statement.on_conflict_do_update(index_elements=["process"], set_=values)
        )

    def get(self, process: str) -> Heartbeat | None:
        record = self._session.get(MonitorHeartbeatRecord, process)
        if record is None:
            return None
        return Heartbeat(
            process=record.process,
            last_cycle_at=record.last_cycle_at,
            last_cycle_duration_ms=record.last_cycle_duration_ms,
            cycle_lag_ms=record.cycle_lag_ms,
            status=ProcessStatus(record.status),
        )


class SchemaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ping(self) -> None:
        self._session.execute(select(1))

    def current_revision(self) -> str | None:
        try:
            return self._session.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
        except SQLAlchemyError:
            self._session.rollback()
            return None
