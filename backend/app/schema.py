"""Complete ORM metadata, for Alembic autogenerate and the migration drift check."""

from app.core.db import Base
from app.identity.repository import AuditEventRecord
from app.monitor.repository import MonitorHeartbeatRecord
from app.topology.repository import PlatformRecord

RECORDS = (AuditEventRecord, MonitorHeartbeatRecord, PlatformRecord)
metadata = Base.metadata
