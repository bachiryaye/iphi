"""Diagnosis contract (architecture §06.1, ADR 0006): every claim cites its own evidence."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DiagnosticKind(StrEnum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"


class DiagnosticStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"


class Uncertainty(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class Citation:
    """An incident evidence row: its ID and its stable `E<n>` label."""

    evidence_id: int
    label: str


@dataclass(frozen=True, slots=True)
class Claim:
    text: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class Hypothesis:
    text: str
    citations: tuple[Citation, ...]
    uncertainty: Uncertainty


@dataclass(frozen=True, slots=True)
class Diagnosis:
    observed_facts: tuple[Claim, ...]
    hypotheses: tuple[Hypothesis, ...]
    recommended_checks: tuple[Claim, ...]
    limitations: tuple[str, ...]
    model: str


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """`removed`: claims dropped because none of their citations is in the evidence set."""

    checked_claims: int
    removed: tuple[str, ...]
    dropped_citations: int


@dataclass(frozen=True, slots=True)
class StoredDiagnostic:
    id: uuid.UUID
    incident_id: uuid.UUID
    kind: DiagnosticKind
    provider: str
    model: str
    status: DiagnosticStatus
    diagnosis: Diagnosis
    evidence_set_hash: str
    validation: ValidationReport
    created_by: str
    created_at: datetime
