"""Complete ORM metadata, for Alembic autogenerate and the migration drift check."""

from app.core.db import Base
from app.identity.repository import AuditEventRecord
from app.ingestion.repository import (
    CollectionCursorRecord,
    CollectionRunRecord,
    LogEventRecord,
    MetricDefinitionRecord,
    MetricSampleRecord,
)
from app.monitor.repository import MonitorHeartbeatRecord
from app.simulation.repository import ScenarioRunRecord, SimClockRecord
from app.topology.repository import ComponentRecord, DependencyRecord, PlatformRecord

RECORDS = (
    AuditEventRecord,
    CollectionCursorRecord,
    CollectionRunRecord,
    ComponentRecord,
    DependencyRecord,
    LogEventRecord,
    MetricDefinitionRecord,
    MetricSampleRecord,
    MonitorHeartbeatRecord,
    PlatformRecord,
    ScenarioRunRecord,
    SimClockRecord,
)
metadata = Base.metadata
