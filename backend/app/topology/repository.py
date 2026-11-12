import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PlatformRecord(Base):
    __tablename__ = "platform"
    # V1 only hosts simulated platforms; lifting this requires an ADR (architecture §03.1).
    __table_args__ = (CheckConstraint("environment = 'simulation'", name="environment_v1"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    environment: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
