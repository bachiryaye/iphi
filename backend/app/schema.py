"""Complete ORM metadata, for Alembic autogenerate and the migration drift check."""

from app.core.db import Base
from app.identity.repository import AuditEventRecord
from app.monitor.repository import MonitorHeartbeatRecord
from app.simulation.repository import ScenarioRunRecord, SimClockRecord
from app.topology.repository import ComponentRecord, DependencyRecord, PlatformRecord

RECORDS = (
    AuditEventRecord,
    ComponentRecord,
    DependencyRecord,
    MonitorHeartbeatRecord,
    PlatformRecord,
    ScenarioRunRecord,
    SimClockRecord,
)
metadata = Base.metadata
