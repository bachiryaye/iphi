import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base, check_in
from app.diagnostics.domain.model import (
    Citation,
    Claim,
    Diagnosis,
    DiagnosticKind,
    DiagnosticStatus,
    Hypothesis,
    StoredDiagnostic,
    Uncertainty,
    ValidationReport,
)

MAX_PROMPT_CHARS = 32_768


class DiagnosticRecord(Base):
    """Append-only: a trigger of migration 0005 rejects UPDATE and DELETE."""

    __tablename__ = "diagnostic"
    __table_args__ = (
        CheckConstraint(check_in("kind", DiagnosticKind), name="kind"),
        CheckConstraint(check_in("status", DiagnosticStatus), name="status"),
        CheckConstraint(
            f"prompt_redacted IS NULL OR char_length(prompt_redacted) <= {MAX_PROMPT_CHARS}",
            name="prompt_bounded",
        ),
        UniqueConstraint("incident_id", "idempotency_key"),
        Index("ix_diagnostic_incident_id_created_at", "incident_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incident.id"))
    kind: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    observed_facts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    hypotheses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    recommended_checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    limitations: Mapped[list[str]] = mapped_column(JSONB)
    evidence_set_hash: Mapped[str] = mapped_column(String(64))
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    prompt_redacted: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime]


class DiagnosticRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, diagnostic: StoredDiagnostic, idempotency_key: str | None) -> None:
        d = diagnostic.diagnosis
        self._session.add(
            DiagnosticRecord(
                id=diagnostic.id,
                incident_id=diagnostic.incident_id,
                kind=diagnostic.kind.value,
                provider=diagnostic.provider,
                model=diagnostic.model,
                status=diagnostic.status.value,
                observed_facts=[_claim(c) for c in d.observed_facts],
                hypotheses=[
                    {**_claim(Claim(h.text, h.citations)), "uncertainty": h.uncertainty.value}
                    for h in d.hypotheses
                ],
                recommended_checks=[_claim(c) for c in d.recommended_checks],
                limitations=list(d.limitations),
                evidence_set_hash=diagnostic.evidence_set_hash,
                validation_report={
                    "checked_claims": diagnostic.validation.checked_claims,
                    "removed": list(diagnostic.validation.removed),
                    "dropped_citations": diagnostic.validation.dropped_citations,
                },
                idempotency_key=idempotency_key,
                created_by=diagnostic.created_by,
                created_at=diagnostic.created_at,
            )
        )
        self._session.flush()

    def by_key(self, incident_id: uuid.UUID, idempotency_key: str) -> StoredDiagnostic | None:
        record = self._session.scalars(
            select(DiagnosticRecord).where(
                DiagnosticRecord.incident_id == incident_id,
                DiagnosticRecord.idempotency_key == idempotency_key,
            )
        ).one_or_none()
        return None if record is None else _to_diagnostic(record)

    def latest(self, incident_id: uuid.UUID, kind: DiagnosticKind) -> StoredDiagnostic | None:
        found = self.of_incident(incident_id, 1, kind)
        return found[0] if found else None

    def of_incident(
        self, incident_id: uuid.UUID, limit: int, kind: DiagnosticKind | None = None
    ) -> list[StoredDiagnostic]:
        """Newest first."""
        statement = select(DiagnosticRecord).where(DiagnosticRecord.incident_id == incident_id)
        if kind is not None:
            statement = statement.where(DiagnosticRecord.kind == kind.value)
        statement = statement.order_by(
            DiagnosticRecord.created_at.desc(), DiagnosticRecord.id.desc()
        ).limit(limit)
        return [_to_diagnostic(r) for r in self._session.scalars(statement)]


def _claim(claim: Claim) -> dict[str, Any]:
    return {
        "text": claim.text,
        "evidence": [{"id": c.evidence_id, "label": c.label} for c in claim.citations],
    }


def _citations(raw: dict[str, Any]) -> tuple[Citation, ...]:
    return tuple(Citation(c["id"], c["label"]) for c in raw["evidence"])


def _to_diagnostic(r: DiagnosticRecord) -> StoredDiagnostic:
    report = r.validation_report
    return StoredDiagnostic(
        id=r.id,
        incident_id=r.incident_id,
        kind=DiagnosticKind(r.kind),
        provider=r.provider,
        model=r.model,
        status=DiagnosticStatus(r.status),
        diagnosis=Diagnosis(
            observed_facts=tuple(Claim(c["text"], _citations(c)) for c in r.observed_facts),
            hypotheses=tuple(
                Hypothesis(h["text"], _citations(h), Uncertainty(h["uncertainty"]))
                for h in r.hypotheses
            ),
            recommended_checks=tuple(Claim(c["text"], _citations(c)) for c in r.recommended_checks),
            limitations=tuple(r.limitations),
            model=r.model,
        ),
        evidence_set_hash=r.evidence_set_hash,
        validation=ValidationReport(
            report["checked_claims"], tuple(report["removed"]), report["dropped_citations"]
        ),
        created_by=r.created_by,
        created_at=r.created_at,
    )
