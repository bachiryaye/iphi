"""Strict provider boundary; labels are resolved from the submitted pack, never model IDs."""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.diagnostics.domain.model import Claim, Diagnosis, Hypothesis, Uncertainty, ValidationReport
from app.diagnostics.evidence import EvidencePack, redact

Text = Annotated[str, Field(min_length=1, max_length=1500)]
Labels = Annotated[list[Annotated[str, Field(max_length=24)]], Field(max_length=20)]


class ClaimIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: Text
    evidence_ids: Labels


class HypothesisIn(ClaimIn):
    uncertainty: Literal["low", "medium", "high"]


class DiagnosisIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    observed_facts: list[ClaimIn] = Field(max_length=12)
    hypotheses: list[HypothesisIn] = Field(max_length=8)
    recommended_checks: list[ClaimIn] = Field(max_length=12)
    limitations: list[Text] = Field(max_length=10)
    model: Annotated[str, Field(min_length=1, max_length=100)]


@dataclass(frozen=True, slots=True)
class Validated:
    diagnosis: Diagnosis
    report: ValidationReport


def validate_reply(raw: str, pack: EvidencePack, model: str) -> Validated:
    parsed = DiagnosisIn.model_validate_json(raw)
    removed: list[str] = []
    dropped = 0

    def claim(item: ClaimIn) -> Claim | None:
        nonlocal dropped
        citations = tuple(
            pack.citations[label]
            for label in dict.fromkeys(item.evidence_ids)
            if label in pack.citations
        )
        dropped += sum(label not in pack.citations for label in item.evidence_ids)
        text = redact(item.text)
        # Reject causal assertions and executable remediation even when the model cites a real ID.
        unsafe = any(
            word in text.casefold()
            for word in (
                "caused by",
                "root cause is",
                "definitely caused",
                "restart ",
                "reboot ",
                "sudo ",
                "systemctl ",
                "docker exec",
                "rm -",
                "curl ",
                "powershell ",
            )
        )
        if not citations or unsafe:
            removed.append(text)
            return None
        return Claim(text, citations)

    facts = tuple(found for item in parsed.observed_facts if (found := claim(item)) is not None)
    hypotheses = tuple(
        Hypothesis(found.text, found.citations, Uncertainty(item.uncertainty))
        for item in parsed.hypotheses
        if (found := claim(item)) is not None
    )
    checks = tuple(
        found for item in parsed.recommended_checks if (found := claim(item)) is not None
    )
    limitations = (
        *(redact(text) for text in parsed.limitations),
        "Simulated environment. AI-generated: verify every claim against its evidence.",
        "Citations validate references, not semantic truth. Correlation is not proven causation.",
    )
    if pack.truncated:
        limitations += ("The evidence pack was truncated to the configured input budget.",)
    return Validated(
        Diagnosis(facts, hypotheses, checks, limitations, model),
        ValidationReport(
            len(parsed.observed_facts) + len(parsed.hypotheses) + len(parsed.recommended_checks),
            tuple(removed),
            dropped,
        ),
    )
