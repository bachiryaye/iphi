import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from app.core.db import create_session_factory
from app.core.settings import LlmProvider, Settings
from app.diagnostics.evidence import EvidencePack
from app.diagnostics.providers import FakeProvider, NoneProvider, ProviderError, ProviderReply
from app.diagnostics.repository import admission
from app.diagnostics.service import DiagnosticRuntime, DiagnosticsService
from app.main import create_app
from app.topology.service import TopologyService
from tests.fakes import FixedClock
from tests.health_runs import Platform

pytestmark = pytest.mark.integration
BASE = "/api/v1/incidents"


@pytest.fixture
def client(seeded_url: str, platform: Platform) -> Iterator[TestClient]:
    app = create_app(
        Settings(
            database_url=SecretStr(seeded_url), dev_mutations=True, llm_provider=LlmProvider.FAKE
        )
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client


def incident_id(client: TestClient) -> str:
    return str(client.get(BASE).json()["items"][0]["id"])


def test_llm_diagnosis_and_same_snapshot_comparison_are_persisted(
    client: TestClient,
    platform: Platform,
) -> None:
    iid = incident_id(client)
    first = client.post(
        f"{BASE}/{iid}/diagnose?mode=llm", json={}, headers={"Idempotency-Key": "first"}
    )
    again = client.post(
        f"{BASE}/{iid}/diagnose?mode=llm", json={}, headers={"Idempotency-Key": "first"}
    )
    assert (first.status_code, again.status_code) == (201, 200), first.text
    result = first.json()
    assert result["id"] == again.json()["id"]
    assert result["kind"] == "llm"
    assert result["status"] == "succeeded"
    assert result["model"] == "fake/evidence-v1"
    listed = client.get(f"{BASE}/{iid}/diagnostics").json()["items"]
    assert listed[0]["id"] == result["id"]
    assert listed[1]["id"] == result["deterministic_id"]
    assert listed[1]["evidence_set_hash"] == result["evidence_set_hash"]
    assert "prompt_redacted" not in result
    assert result["input_tokens"] is None
    assert result["output_tokens"] is None
    assert result["latency_ms"] >= 0
    assert platform.rows("SELECT attempts FROM diagnostic_budget")[0][0] == 1
    assert len(platform.rows("SELECT id FROM diagnostic")) == 2
    check = client.get("/api/v1/system/status").json()["ai_provider"]
    assert check["status"] == "ok"


class ScriptedProvider(FakeProvider):
    def __init__(self, outcome: str, platform: Platform | None = None) -> None:
        self.outcome, self.platform = outcome, platform

    async def generate(self, pack: EvidencePack) -> ProviderReply:
        if self.outcome == "timeout":
            raise ProviderError("LLM_TIMEOUT")
        if self.outcome == "unavailable":
            raise ProviderError("LLM_TRANSPORT_ERROR", retryable=True)
        if self.outcome == "invalid":
            return ProviderReply("invalid json")
        if self.platform is not None:
            # Fails immediately if a diagnostic holds the row lock across the provider call.
            with self.platform.engine.begin() as connection:
                connection.execute(text("SET LOCAL lock_timeout = '1s'"))
                connection.execute(text("SELECT id FROM incident FOR UPDATE NOWAIT"))
            self.platform.advance(30)
        generated = await super().generate(pack)
        if self.outcome == "invented":
            parsed = json.loads(generated.text)
            parsed["observed_facts"].append({"text": "Invented fact", "evidence_ids": ["E999999"]})
            return ProviderReply(json.dumps(parsed))
        return generated


def use_provider(
    client: TestClient, platform: Platform, provider: FakeProvider, wall: FixedClock | None = None
) -> None:
    factory = create_session_factory(platform.engine)
    settings = Settings(database_url=SecretStr("unused"), llm_provider=LlmProvider.FAKE)
    service = DiagnosticsService(
        factory,
        wall or FixedClock(datetime(2026, 11, 17, tzinfo=UTC)),
        lambda: platform.simulation.clock().platform_time,
        TopologyService(factory),
        DiagnosticRuntime(settings, provider),
    )
    assert isinstance(client.app, FastAPI)
    client.app.state.diagnostics = service


@pytest.mark.parametrize(
    ("outcome", "status", "code"),
    [
        ("invalid", "rejected", "LLM_INVALID_JSON"),
        ("timeout", "failed", "LLM_TIMEOUT"),
        ("unavailable", "failed", "LLM_TRANSPORT_ERROR"),
    ],
)
def test_failure_is_persisted_with_functional_deterministic_fallback(
    client: TestClient,
    platform: Platform,
    outcome: str,
    status: str,
    code: str,
) -> None:
    use_provider(client, platform, ScriptedProvider(outcome))
    iid = incident_id(client)
    response = client.post(f"{BASE}/{iid}/diagnose?mode=llm", json={})
    assert response.status_code == 201, response.text
    result = response.json()
    assert (result["status"], result["error_code"]) == (status, code)
    fallback = next(
        item
        for item in client.get(f"{BASE}/{iid}/diagnostics").json()["items"]
        if item["id"] == result["deterministic_id"]
    )
    assert fallback["kind"] == "deterministic"
    assert fallback["observed_facts"]
    assert client.get(BASE).status_code == 200
    assert platform.component_state("collector-01").value == "critical"


def test_invented_claim_is_removed_without_losing_supported_claims(
    client: TestClient,
    platform: Platform,
) -> None:
    use_provider(client, platform, ScriptedProvider("invented"))
    response = client.post(f"{BASE}/{incident_id(client)}/diagnose?mode=llm", json={})
    assert response.status_code == 201, response.text
    assert response.json()["validation"]["removed"] == ["Invented fact"]
    assert response.json()["status"] == "succeeded"


def test_worker_progresses_while_the_provider_is_waiting(
    client: TestClient, platform: Platform
) -> None:
    use_provider(client, platform, ScriptedProvider("success", platform))
    before = platform.simulation.clock().platform_time
    response = client.post(f"{BASE}/{incident_id(client)}/diagnose?mode=llm", json={})
    assert response.status_code == 201, response.text
    assert platform.simulation.clock().platform_time > before
    assert response.json()["status"] == "succeeded"


def test_budget_survives_service_recreation_and_replay_does_not_charge(
    client: TestClient,
    platform: Platform,
) -> None:
    iid = incident_id(client)
    wall = FixedClock(datetime(2026, 11, 17, tzinfo=UTC))
    for number in range(6):
        use_provider(client, platform, FakeProvider(), wall)
        response = client.post(
            f"{BASE}/{iid}/diagnose?mode=llm",
            json={},
            headers={"Idempotency-Key": f"attempt-{number}"},
        )
        assert response.status_code == 201, response.text
    replay = client.post(
        f"{BASE}/{iid}/diagnose?mode=llm", json={}, headers={"Idempotency-Key": "attempt-0"}
    )
    refused = client.post(f"{BASE}/{iid}/diagnose?mode=llm", json={})
    assert replay.status_code == 200
    assert refused.status_code == 429
    assert refused.json()["code"] == "DIAGNOSIS_RATE_LIMITED"
    assert platform.rows("SELECT attempts FROM diagnostic_budget")[0][0] == 6
    deterministic = client.post(f"{BASE}/{iid}/diagnose", json={})
    assert deterministic.status_code == 200
    assert (
        platform.rows(
            "SELECT outcome FROM audit_event WHERE details->>'error_code' "
            "= 'DIAGNOSIS_RATE_LIMITED'"
        )[0][0]
        == "failed"
    )

    wall.current += timedelta(seconds=60)
    allowed = client.post(f"{BASE}/{iid}/diagnose?mode=llm", json={})
    assert allowed.status_code == 201
    assert platform.rows("SELECT attempts FROM diagnostic_budget")[0][0] == 1


def test_concurrent_llm_request_is_refused_without_blocking_incident_updates(
    client: TestClient,
    platform: Platform,
) -> None:
    iid = incident_id(client)
    with admission(create_session_factory(platform.engine), uuid.UUID(iid), "another-actor"):
        response = client.post(f"{BASE}/{iid}/diagnose?mode=llm", json={})
        assert response.status_code == 409
        assert response.json()["code"] == "DIAGNOSIS_IN_PROGRESS"
        assert client.post(f"{BASE}/{iid}/ack", json={}).status_code == 200


def test_disabled_provider_has_a_fallback_and_does_not_break_readiness(
    client: TestClient,
    platform: Platform,
) -> None:
    factory = create_session_factory(platform.engine)
    settings = Settings(database_url=SecretStr("unused"))
    service = DiagnosticsService(
        factory,
        FixedClock(datetime(2026, 11, 17, tzinfo=UTC)),
        lambda: platform.simulation.clock().platform_time,
        TopologyService(factory),
        DiagnosticRuntime(settings, NoneProvider()),
    )
    assert isinstance(client.app, FastAPI)
    client.app.state.diagnostics = service
    iid = incident_id(client)
    response = client.post(f"{BASE}/{iid}/diagnose?mode=llm", json={})
    assert response.status_code == 201
    assert response.json()["error_code"] == "LLM_DISABLED"
    assert response.json()["deterministic_id"] is not None
    assert service.provider_status().status.value == "disabled"


def test_idempotency_key_cannot_be_reused_for_another_mode(client: TestClient) -> None:
    iid = incident_id(client)
    headers = {"Idempotency-Key": "same-key"}
    assert client.post(f"{BASE}/{iid}/diagnose", json={}, headers=headers).status_code == 201
    conflict = client.post(f"{BASE}/{iid}/diagnose?mode=llm", json={}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "DIAGNOSIS_KEY_CONFLICT"


def test_cited_evidence_beyond_the_first_page_keeps_its_label(
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
                "WHERE e.incident_id = :iid AND e.metric_sample_id = s.id) "
                "ORDER BY s.id LIMIT 205"
            ),
            {"iid": uuid.UUID(iid)},
        )
    detail = client.get(f"{BASE}/{iid}").json()
    assert detail["evidence_count"] > 200
    last = platform.rows(
        "SELECT max(id) FROM incident_evidence WHERE incident_id=:iid", iid=uuid.UUID(iid)
    )[0][0]
    assert last not in [item["id"] for item in detail["evidence"]]
    proof = client.get(f"{BASE}/{iid}/evidence", params={"evidence_id": last}).json()
    assert len(proof["items"]) == 1
    assert proof["items"][0]["label"] == f"E{detail['evidence_count']}"
    assert proof["next_cursor"] is None
    assert client.get(f"{BASE}/{iid}/evidence", params={"evidence_id": 2**63}).status_code == 422
    assert (
        client.get(f"{BASE}/{iid}/evidence", params={"evidence_id": last + 1}).json()["items"] == []
    )
