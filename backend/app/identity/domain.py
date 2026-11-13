import ipaddress
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from http import HTTPStatus
from typing import Any

from app.core.exceptions import IphiError

# ADR 0007: the only actor before US-11; every mutation is attributed to it.
DEV_ACTOR = "dev-local"


class AuditAction(StrEnum):
    """Audited mutations; the same value names the denied, allowed and failed rows."""

    SCENARIO_START = "scenario.start"
    SCENARIO_STOP = "scenario.stop"
    SIMULATION_RESET = "simulation.reset"
    CLOCK_UPDATE = "clock.update"
    INCIDENT_ACK = "incident.ack"
    INCIDENT_RESOLVE = "incident.resolve"
    INCIDENT_DIAGNOSE = "incident.diagnose"


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


class MutationsDisabledError(IphiError):
    status = HTTPStatus.FORBIDDEN
    code = "MUTATIONS_DISABLED"


@dataclass(frozen=True, slots=True)
class MutationPolicy:
    """ADR 0007, before US-11: mutations need IPHI_DEV_MUTATIONS and loopback-only publishing."""

    enabled: bool
    reason: str

    @classmethod
    def evaluate(cls, dev_mutations: bool, bind_host: str) -> MutationPolicy:
        if not dev_mutations:
            return cls(
                False, "Mutations are disabled; set IPHI_DEV_MUTATIONS=true on a local host."
            )
        if not _is_loopback(bind_host):
            return cls(
                False,
                f"Mutations are disabled: the API is published on {bind_host}, not loopback.",
            )
        return cls(True, "Local development mutations enabled (unauthenticated, ADR 0007).")

    def enforce(self) -> None:
        if not self.enabled:
            raise MutationsDisabledError(self.reason)


def _is_loopback(host: str) -> bool:
    # IP literals only: Compose port bindings do not resolve host names.
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
