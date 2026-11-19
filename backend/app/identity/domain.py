import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class AuditAction(StrEnum):
    """Audited mutations; the same value names the denied, allowed and failed rows."""

    SCENARIO_START = "scenario.start"
    SCENARIO_STOP = "scenario.stop"
    SIMULATION_RESET = "simulation.reset"
    CLOCK_UPDATE = "clock.update"
    INCIDENT_ACK = "incident.ack"
    INCIDENT_RESOLVE = "incident.resolve"
    INCIDENT_DIAGNOSE = "incident.diagnose"
    INCIDENT_COMMENT = "incident.comment"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUDIT_READ = "audit.read"
    USER_SEED = "identity.user.seed"
    PASSWORD_ROTATE = "identity.password.rotate"  # noqa: S105 - Audit action, not a credential.


class AuditOutcome(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AuditContext:
    """Who asks, and the request correlation ID that ties the audit row to the logs."""

    actor_label: str
    correlation_id: str | None
    actor_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class AuditEntry:
    context: AuditContext
    action: AuditAction
    outcome: AuditOutcome
    occurred_at: datetime
    platform_time: datetime | None
    target_type: str | None
    target_id: str | None
    details: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: uuid.UUID
    entry: AuditEntry


@dataclass(frozen=True, slots=True)
class MutationPolicy:
    """Role-based availability shown to the signed-in operator; routes enforce RBAC separately."""

    enabled: bool
    reason: str
