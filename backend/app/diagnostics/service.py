import asyncio
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

import structlog
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.settings import Settings
from app.diagnostics.domain.deterministic import (
    MODEL,
    PROVIDER,
    DiagnosisInput,
    RelatedIncident,
    diagnose,
    evidence_set_hash,
    validate,
)
from app.diagnostics.domain.errors import DiagnosisKeyConflictError
from app.diagnostics.domain.model import (
    Diagnosis,
    DiagnosticKind,
    DiagnosticStatus,
    StoredDiagnostic,
    ValidationReport,
)
from app.diagnostics.evidence import SYSTEM_PROMPT, build_pack
from app.diagnostics.providers import Provider, ProviderError, bounded_call, build_provider
from app.diagnostics.repository import DiagnosticRepository, admission, charge
from app.diagnostics.validation import DiagnosisIn, validate_reply
from app.identity.domain import AuditAction, AuditContext
from app.identity.service import AuditedMutations
from app.incidents.domain.model import Incident
from app.incidents.service import IncidentHistory, actor_of
from app.monitor.domain import CheckName, CheckStatus, ReadinessCheck
from app.topology.domain import PlatformNotFoundError, PlatformTopology, upstream_ids
from app.topology.service import TopologyService

# Evaluations per role group: with one observation each, at most 40 items (§06.2: <= 50).
KEY_EVALUATIONS = 10
MAX_RELATED = 10
MAX_LISTED = 50

log = structlog.get_logger(__name__)


class DiagnosticReader:
    def __init__(self, session: Session) -> None:
        self._repository = DiagnosticRepository(session)

    def for_report(self, incident_id: uuid.UUID) -> tuple[StoredDiagnostic, ...]:
        """Latest of each kind, plus the latest LLM's comparison, in the caller's snapshot."""
        found = [
            item
            for kind in DiagnosticKind
            if (item := self._repository.latest(incident_id, kind)) is not None
        ]
        reference = next((item.deterministic_id for item in found if item.deterministic_id), None)
        if reference and all(item.id != reference for item in found):
            comparison = self._repository.get(reference)
            if comparison is not None:
                found.append(comparison)
        return tuple(found)


@dataclass(frozen=True, slots=True)
class DiagnosisResult:
    diagnostic: StoredDiagnostic
    created: bool


@dataclass(frozen=True, slots=True)
class DiagnosticRuntime:
    settings: Settings
    provider: Provider


class DiagnosticsService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        wall: Clock,
        platform_now: Callable[[], datetime],
        topology: TopologyService,
        runtime: DiagnosticRuntime | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._audited = AuditedMutations(session_factory, wall)
        self._platform_now = platform_now
        self._topology = topology
        self._wall = wall
        self._settings = runtime.settings if runtime else Settings(database_url="unused")
        self._provider = runtime.provider if runtime else build_provider(self._settings)

    def provider_status(self) -> ReadinessCheck:
        if self._provider.name == "none":
            return ReadinessCheck(
                CheckName.AI_PROVIDER,
                CheckStatus.DISABLED,
                "LLM provider 'none'; deterministic diagnosis only.",
            )
        try:
            with self._session_factory() as session:
                last = DiagnosticRepository(session).latest_llm(self._provider.name)
        except SQLAlchemyError:
            last = None
        if last is None:
            return ReadinessCheck(
                CheckName.AI_PROVIDER,
                CheckStatus.UNKNOWN,
                f"AI provider {self._provider.name} configured; no completed attempt observed.",
            )
        status = CheckStatus.OK if last.status is DiagnosticStatus.SUCCEEDED else CheckStatus.FAILED
        return ReadinessCheck(
            CheckName.AI_PROVIDER,
            status,
            f"Last {self._provider.name} attempt: {last.status.value}. "
            "Deterministic diagnosis remains available.",
            last.created_at,
        )

    def diagnose(
        self,
        incident_id: uuid.UUID,
        kind: DiagnosticKind,
        idempotency_key: str | None,
        context: AuditContext,
    ) -> DiagnosisResult:
        """Same key returns the stored result; deterministic mode also reuses unchanged evidence."""
        if kind is DiagnosticKind.LLM:
            return self._llm(incident_id, idempotency_key, context)
        with self._audited.run(context, AuditAction.INCIDENT_DIAGNOSE) as work:
            work.audit.target_type, work.audit.target_id = "incident", str(incident_id)
            work.audit.details["kind"] = kind.value
            history = IncidentHistory(work.session)
            incident = history.lock(incident_id)
            work.audit.platform_time = at = self._platform_now()
            diagnostics = DiagnosticRepository(work.session)
            if idempotency_key is not None:
                existing = diagnostics.by_key(incident_id, idempotency_key)
                if existing is not None:
                    if existing.kind is not kind:
                        raise DiagnosisKeyConflictError(
                            "The key was already used for another diagnosis mode."
                        )
                    work.audit.details["reused"] = str(existing.id)
                    return DiagnosisResult(existing, created=False)
            data = self._input(history, incident)
            digest = evidence_set_hash(data)
            latest = diagnostics.latest(incident_id, DiagnosticKind.DETERMINISTIC)
            if (
                idempotency_key is None
                and latest is not None
                and latest.evidence_set_hash == digest
            ):
                work.audit.details["reused"] = str(latest.id)
                return DiagnosisResult(latest, created=False)
            diagnosis, report = validate(diagnose(data), {i.stored.id for i in data.evidence})
            stored = StoredDiagnostic(
                id=uuid.uuid7(),
                incident_id=incident_id,
                kind=DiagnosticKind.DETERMINISTIC,
                provider=PROVIDER,
                model=MODEL,
                status=DiagnosticStatus.SUCCEEDED,
                diagnosis=diagnosis,
                evidence_set_hash=digest,
                validation=report,
                created_by=context.actor_label,
                created_at=at,
            )
            diagnostics.add(stored, idempotency_key)
            history.record_diagnostic(
                incident, (stored.id, stored.kind.value), actor_of(context), at
            )
            work.audit.details["diagnostic_id"] = str(stored.id)
        log.info("diagnostic.created", incident_id=incident_id, diagnostic_id=stored.id)
        return DiagnosisResult(stored, created=True)

    def _llm(
        self,
        incident_id: uuid.UUID,
        key: str | None,
        context: AuditContext,
    ) -> DiagnosisResult:
        with self._audited.run(context, AuditAction.INCIDENT_DIAGNOSE) as work:
            work.audit.target_type, work.audit.target_id = "incident", str(incident_id)
            work.audit.details["kind"] = DiagnosticKind.LLM.value
            with admission(self._session_factory, incident_id, context.actor_label):
                with self._session_factory.begin() as session:
                    history = IncidentHistory(session)
                    incident = history.lock(incident_id)
                    existing = (
                        DiagnosticRepository(session).by_key(incident_id, key) if key else None
                    )
                    if existing is not None:
                        if existing.kind is not DiagnosticKind.LLM:
                            raise DiagnosisKeyConflictError(
                                "The key was already used for another diagnosis mode."
                            )
                        work.audit.details["reused"] = str(existing.id)
                        return DiagnosisResult(existing, created=False)
                    data = self._input(history, incident)
                    charge(session, context.actor_label, self._wall.now())
                # Snapshot and budget have committed; the worker can update this incident now.
                attempt = self._attempt(data, context.actor_label)
                history = IncidentHistory(work.session)
                current = history.lock(incident_id)
                work.audit.platform_time = at = self._platform_now()
                repository = DiagnosticRepository(work.session)
                baseline = self._baseline(repository, data, context.actor_label, at)
                if baseline[1]:
                    history.record_diagnostic(
                        current, (baseline[0].id, "deterministic"), actor_of(context), at
                    )
                stored = replace(
                    attempt, id=uuid.uuid7(), deterministic_id=baseline[0].id, created_at=at
                )
                repository.add(stored, key)
                history.record_diagnostic(current, (stored.id, "llm"), actor_of(context), at)
                work.audit.details.update(
                    diagnostic_id=str(stored.id),
                    status=stored.status.value,
                    error_code=stored.error_code,
                )
        log.info(
            "diagnostic.created",
            incident_id=incident_id,
            diagnostic_id=stored.id,
            kind="llm",
            status=stored.status.value,
            error_code=stored.error_code,
        )
        return DiagnosisResult(stored, created=True)

    def _baseline(
        self,
        repository: DiagnosticRepository,
        data: DiagnosisInput,
        actor: str,
        at: datetime,
    ) -> tuple[StoredDiagnostic, bool]:
        digest = evidence_set_hash(data)
        latest = repository.latest(data.incident.id, DiagnosticKind.DETERMINISTIC)
        if latest is not None and latest.evidence_set_hash == digest:
            return latest, False
        diagnosis, report = validate(diagnose(data), {i.stored.id for i in data.evidence})
        stored = StoredDiagnostic(
            uuid.uuid7(),
            data.incident.id,
            DiagnosticKind.DETERMINISTIC,
            PROVIDER,
            MODEL,
            DiagnosticStatus.SUCCEEDED,
            diagnosis,
            digest,
            report,
            actor,
            at,
        )
        repository.add(stored, None)
        return stored, True

    def _attempt(self, data: DiagnosisInput, actor: str) -> StoredDiagnostic:
        schema_bytes = len(json.dumps(DiagnosisIn.model_json_schema()).encode())
        pack = build_pack(data, self._settings.llm_input_tokens - schema_bytes - 512)
        started = time.perf_counter()
        status, code = DiagnosticStatus.SUCCEEDED, None
        diagnosis = Diagnosis((), (), (), (), self._provider.model)
        report = ValidationReport(0, (), 0)
        reply = None
        try:
            if not pack.citations:
                raise ProviderError("LLM_NO_EVIDENCE")
            reply = asyncio.run(bounded_call(self._provider, pack, self._settings.llm_timeout_s))
            if (
                reply.input_tokens is not None
                and reply.input_tokens > self._settings.llm_input_tokens
            ) or (
                reply.output_tokens is not None
                and reply.output_tokens > self._settings.llm_output_tokens
            ):
                raise ProviderError("LLM_TOKEN_BUDGET")
            validated = validate_reply(reply.text, pack, self._provider.model)
            diagnosis, report = validated.diagnosis, validated.report
            if not diagnosis.observed_facts:
                status, code = DiagnosticStatus.REJECTED, "LLM_NO_SUPPORTED_FACTS"
        except ValidationError:
            status, code = DiagnosticStatus.REJECTED, "LLM_INVALID_JSON"
        except ProviderError as exc:
            status, code = DiagnosticStatus.FAILED, exc.code
        if status is not DiagnosticStatus.SUCCEEDED:
            diagnosis = replace(
                diagnosis,
                limitations=(
                    "AI diagnosis unavailable or rejected. Use the linked deterministic diagnosis.",
                    "Simulated environment; model output never changes health or incidents.",
                ),
            )
        return StoredDiagnostic(
            uuid.uuid7(),
            data.incident.id,
            DiagnosticKind.LLM,
            self._provider.name,
            self._provider.model,
            status,
            diagnosis,
            evidence_set_hash(data),
            report,
            actor,
            data.incident.last_seen_at,
            prompt_redacted=SYSTEM_PROMPT + "\n" + pack.prompt,
            input_tokens=None if reply is None else reply.input_tokens,
            output_tokens=None if reply is None else reply.output_tokens,
            latency_ms=round((time.perf_counter() - started) * 1000),
            error_code=code,
        )

    def of_incident(self, incident_id: uuid.UUID) -> list[StoredDiagnostic]:
        with self._session_factory() as session:
            IncidentHistory(session).find(incident_id)
            repository = DiagnosticRepository(session)
            result = repository.of_incident(incident_id, MAX_LISTED)
            reference = result[0].deterministic_id if result else None
            if reference and all(item.id != reference for item in result):
                comparison = repository.get(reference)
                if comparison is not None:
                    result.append(comparison)
            return result

    def _input(self, history: IncidentHistory, incident: Incident) -> DiagnosisInput:
        topology = self._platform(incident.platform_id)
        keys = topology.keys_by_id()
        upstream = upstream_ids(incident.component_id, topology.dependencies)
        end = incident.resolved_at or incident.last_seen_at
        related = [
            RelatedIncident(
                r, keys[r.component_id], len(upstream_ids(r.component_id, topology.dependencies))
            )
            for r in history.related(upstream, incident.opened_at, end, MAX_RELATED)
        ]
        return DiagnosisInput(
            incident=incident,
            component_keys=keys,
            evidence=history.key_evidence(incident.id, KEY_EVALUATIONS),
            impacted=[keys[i.component_id] for i in history.impacts(incident.id)],
            related=related,
            logs_attached=history.has_log_evidence(incident.id),
        )

    def _platform(self, platform_id: uuid.UUID) -> PlatformTopology:
        found = next((t for t in self._topology.platforms() if t.platform_id == platform_id), None)
        if found is None:
            raise PlatformNotFoundError(f"No platform {platform_id}.")
        return found
