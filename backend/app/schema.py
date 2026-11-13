"""Complete ORM metadata, for Alembic autogenerate and the migration drift check."""

from app.core.db import Base
from app.diagnostics.repository import DiagnosticRecord
from app.health.repository import (
    ComponentHealthRecord,
    HealthRuleRecord,
    PlatformHealthRecord,
    RuleEvaluationRecord,
    RuleStateRecord,
)
from app.identity.repository import AuditEventRecord
from app.incidents.repository import (
    IncidentEventRecord,
    IncidentEvidenceRecord,
    IncidentImpactRecord,
    IncidentRecord,
)
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
    ComponentHealthRecord,
    ComponentRecord,
    DependencyRecord,
    DiagnosticRecord,
    HealthRuleRecord,
    IncidentEventRecord,
    IncidentEvidenceRecord,
    IncidentImpactRecord,
    IncidentRecord,
    LogEventRecord,
    MetricDefinitionRecord,
    MetricSampleRecord,
    MonitorHeartbeatRecord,
    PlatformHealthRecord,
    PlatformRecord,
    RuleEvaluationRecord,
    RuleStateRecord,
    ScenarioRunRecord,
    SimClockRecord,
)
metadata = Base.metadata
