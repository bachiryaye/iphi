import csv
import io
import uuid
from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pypdf import PdfReader
from sqlalchemy import text

from app.core.clock import WallClock
from app.core.db import create_session_factory
from app.core.settings import LlmProvider, Settings
from app.main import create_app
from app.reporting.domain import (
    ReportBusyError,
    ReportFormat,
    ReportRenderError,
    ReportSnapshot,
    ReportTooLargeError,
)
from app.reporting.pdf import report_html
from app.reporting.service import ReportingService
from app.topology.service import TopologyService
from tests.api_client import client_for
from tests.health_runs import Platform

pytestmark = pytest.mark.integration
BASE = "/api/v1/reports/incidents"


@pytest.fixture
def client(seeded_url: str, platform: Platform) -> Iterator[TestClient]:
    with client_for(seeded_url, dev_mutations=True) as client:
        yield client


def incident_id(client: TestClient) -> str:
    return str(client.get("/api/v1/incidents").json()["items"][0]["id"])


def reporting(client: TestClient) -> ReportingService:
    assert isinstance(client.app, FastAPI)
    service: ReportingService = client.app.state.reporting
    return service


@pytest.mark.parametrize("format", ["pdf", "csv"])
def test_report_uses_stored_evidence_rules_events_and_separate_diagnoses(
    client: TestClient,
    platform: Platform,
    format: str,
) -> None:
    iid = incident_id(client)
    diagnosis = client.post(f"/api/v1/incidents/{iid}/diagnose", json={}).json()
    service = reporting(client)
    snapshot = service.snapshot(uuid.UUID(iid))
    response = client.get(f"{BASE}/{iid}", params={"format": format})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-iphi-environment"] == "simulation"
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="IPHI-INC-0001-simulated.{format}"'
    )
    if format == "pdf":
        assert response.content.startswith(b"%PDF-")
        reader = PdfReader(io.BytesIO(response.content))
        output = "\n".join(page.extract_text() for page in reader.pages)
        assert all("SIMULATED ENVIRONMENT" in page.extract_text() for page in reader.pages)
        assert "Deterministic diagnosis" in output
        assert "AI-generated" not in output
        for proof in snapshot.facts.evidence:
            assert f"evidence #{proof.stored.id}" in output
        assert len(reader.pages) > 1
    else:
        assert response.headers["content-type"].startswith("text/csv")
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        evidence = [row for row in rows if row["record_type"] == "evidence"]
        events = [row for row in rows if row["record_type"] == "event"]
        assert [int(row["id"]) for row in evidence] == [
            item.stored.id for item in snapshot.facts.evidence
        ]
        assert [int(row["id"]) for row in events] == [item.id for item in snapshot.facts.events]
        assert all(row["environment"] == "simulation" for row in rows)
        assert {row["observation_id"] for row in evidence} == {
            str(item.stored.evaluation_id or item.stored.sample_id or item.stored.log_id)
            for item in snapshot.facts.evidence
        }
        output = response.content.decode("utf-8-sig")
    assert "R-AVAIL-001" in output
    assert diagnosis["id"] in output
    assert "collector-01" in output
    assert "causation is not proven" in " ".join(output.split())
    assert "prompt_redacted" not in output
    assert platform.rows("SELECT count(*) FROM diagnostic")[0][0] == 1


def test_report_read_is_available_when_mutations_are_disabled(
    client: TestClient,
    seeded_url: str,
) -> None:
    iid = incident_id(client)
    with client_for(seeded_url, dev_mutations=False) as viewer:
        assert viewer.get(f"{BASE}/{iid}?format=csv").status_code == 200
        assert viewer.post(f"/api/v1/incidents/{iid}/diagnose", json={}).status_code == 403


def test_pdf_labels_fake_ai_and_preserves_deterministic_fallback(
    client: TestClient,
    seeded_url: str,
) -> None:
    iid = incident_id(client)
    app = create_app(
        Settings(
            database_url=SecretStr(seeded_url),
            dev_mutations=True,
            llm_provider=LlmProvider.FAKE,
        )
    )
    with TestClient(app, base_url="http://127.0.0.1") as fake:
        diagnosis = fake.post(f"/api/v1/incidents/{iid}/diagnose?mode=llm", json={}).json()
        assert diagnosis["status"] == "succeeded"
        output = fake.get(f"{BASE}/{iid}?format=pdf")
        assert output.status_code == 200
        body = " ".join(
            " ".join(
                page.extract_text() for page in PdfReader(io.BytesIO(output.content)).pages
            ).split()
        )
        assert "AI-generated — verify against evidence" in body
        assert "Local fake provider" in body
        assert "Deterministic diagnosis" in body
        assert diagnosis["deterministic_id"] in body
    failure = client.post(f"/api/v1/incidents/{iid}/diagnose?mode=llm", json={}).json()
    assert failure["error_code"] == "LLM_DISABLED"
    output = client.get(f"{BASE}/{iid}?format=pdf")
    assert output.status_code == 200
    body = " ".join(
        " ".join(
            page.extract_text() for page in PdfReader(io.BytesIO(output.content)).pages
        ).split()
    )
    assert "LLM_DISABLED" in body
    assert "Deterministic diagnosis" in body
    rows = list(
        csv.DictReader(
            io.StringIO(client.get(f"{BASE}/{iid}?format=csv").content.decode("utf-8-sig"))
        )
    )
    meta = [row for row in rows if row["record_type"] == "diagnostic_meta"]
    assert {row["diagnosis_kind"] for row in meta} == {"llm", "deterministic"}
    assert (
        next(row for row in meta if row["diagnosis_kind"] == "llm")["error_code"] == "LLM_DISABLED"
    )


def test_invalid_format_and_unknown_incident_return_problem_details(client: TestClient) -> None:
    iid = incident_id(client)
    assert client.get(f"{BASE}/{iid}?format=html").status_code == 422
    missing = client.get(f"{BASE}/{uuid.uuid4()}?format=csv")
    assert missing.status_code == 404
    assert missing.json()["code"] == "INCIDENT_NOT_FOUND"


def test_untrusted_log_is_escaped_in_pdf_and_neutralized_in_csv(
    client: TestClient,
    platform: Platform,
) -> None:
    iid = incident_id(client)
    attack = '=HYPERLINK("https://example.com","<img src=file:///etc/passwd>")'
    with platform.engine.begin() as connection:
        log_id = connection.scalar(text("SELECT id FROM log_event ORDER BY id LIMIT 1"))
        assert log_id is not None
        connection.execute(
            text("UPDATE log_event SET message=:attack WHERE id=:id"),
            {"attack": attack, "id": log_id},
        )
        connection.execute(
            text(
                "INSERT INTO incident_evidence (incident_id, log_event_id, role, added_at) "
                "SELECT :iid, id, 'supporting', observed_at FROM log_event WHERE id=:id "
                "ON CONFLICT DO NOTHING"
            ),
            {"iid": uuid.UUID(iid), "id": log_id},
        )
    service = reporting(client)
    snapshot = service.snapshot(uuid.UUID(iid))
    html = report_html(snapshot)
    assert "<img src=file" not in html
    assert "&lt;img" in html
    response = client.get(f"{BASE}/{iid}?format=csv")
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert next(row for row in rows if row["type"] == "log")["text"] == "'" + attack
    assert client.get(f"{BASE}/{iid}?format=pdf").status_code == 200


def test_evidence_after_the_ui_page_is_exported_and_overflow_is_explicit(
    client: TestClient,
    platform: Platform,
) -> None:
    iid = incident_id(client)
    with platform.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO incident_evidence (incident_id, metric_sample_id, role, added_at) "
                "SELECT :iid, s.id, 'supporting', s.observed_at FROM metric_sample s "
                "WHERE NOT EXISTS (SELECT 1 FROM incident_evidence e "
                "WHERE e.incident_id=:iid AND e.metric_sample_id=s.id) "
                "ORDER BY s.id LIMIT 205"
            ),
            {"iid": uuid.UUID(iid)},
        )
    detail = client.get(f"/api/v1/incidents/{iid}").json()
    exported = client.get(f"{BASE}/{iid}?format=csv")
    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert (
        len([row for row in rows if row["record_type"] == "evidence"])
        == detail["evidence_count"]
        > 200
    )
    with platform.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO incident_evidence (incident_id, metric_sample_id, role, added_at) "
                "SELECT :iid, s.id, 'supporting', s.observed_at FROM metric_sample s "
                "WHERE NOT EXISTS (SELECT 1 FROM incident_evidence e "
                "WHERE e.incident_id=:iid AND e.metric_sample_id=s.id) "
                "ORDER BY s.id LIMIT 1001"
            ),
            {"iid": uuid.UUID(iid)},
        )
    refused = client.get(f"{BASE}/{iid}?format=csv")
    assert refused.status_code == 413
    assert refused.json()["code"] == "REPORT_TOO_LARGE"


def test_report_html_content_limit_refuses_an_excessive_render(client: TestClient) -> None:
    service = reporting(client)
    snapshot = service.snapshot(uuid.UUID(incident_id(client)))
    oversized = replace(snapshot.topology, name="x" * 2_000_001)
    with pytest.raises(ReportTooLargeError):
        report_html(replace(snapshot, topology=oversized))


def test_pdf_admission_keeps_csv_available_and_releases_after_render_failure(
    client: TestClient,
    platform: Platform,
) -> None:
    iid = uuid.UUID(incident_id(client))
    factory = create_session_factory(platform.engine)

    class FailingRenderer:
        def pdf(self, snapshot: ReportSnapshot) -> bytes:
            with pytest.raises(ReportBusyError):
                service.export(iid, ReportFormat.PDF)
            csv = service.export(iid, ReportFormat.CSV)
            assert b'"evidence"' in csv.content
            with platform.engine.begin() as connection:
                connection.execute(text("SELECT id FROM incident FOR UPDATE NOWAIT"))
            raise ReportRenderError("Test rendering failure.")

    service = ReportingService(factory, WallClock(), TopologyService(factory), FailingRenderer())
    for _ in range(2):
        with pytest.raises(ReportRenderError):
            service.export(iid, ReportFormat.PDF)
