import csv
import io

from app.reporting.domain import ReportSnapshot
from app.reporting.presentation import present

COLUMNS = (
    "record_type",
    "id",
    "label",
    "type",
    "occurred_at_utc",
    "added_at_utc",
    "component",
    "source",
    "role",
    "state",
    "metric",
    "value",
    "unit",
    "quality",
    "observation_id",
    "rule_key",
    "rule_version",
    "text",
    "recommendation",
    "details",
    "evidence_ids",
    "diagnostic_id",
    "diagnosis_kind",
    "model",
    "status",
    "uncertainty",
    "environment",
    "incident_id",
    "incident_reference",
    "scenario_run_id",
    "snapshot_at_utc",
    "provider",
    "error_code",
    "deterministic_id",
    "evidence_set_hash",
)


def safe_cell(value: str) -> str:
    """Preserve text while preventing spreadsheet formula interpretation (X-08)."""
    stripped = value.lstrip(" \t\r\n\ufeff")
    if value.startswith(("\t", "\r", "\n")) or stripped.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def csv_report(snapshot: ReportSnapshot) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for row in present(snapshot).records:
        writer.writerow({key: safe_cell(value) for key, value in row.items()})
    return output.getvalue().encode("utf-8-sig")
