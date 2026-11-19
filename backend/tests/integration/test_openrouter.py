import json
from datetime import UTC, datetime

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.db import create_session_factory
from app.core.settings import LlmProvider, Settings
from app.diagnostics.providers import OpenRouterProvider
from app.diagnostics.service import DiagnosticRuntime, DiagnosticsService
from app.main import create_app
from app.topology.service import TopologyService
from tests.api_client import sign_in
from tests.fakes import FixedClock
from tests.health_runs import Platform
from tests.unit.test_llm_diagnosis import reply

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(("cost", "expected"), [(0, "succeeded"), (None, "failed")])
def test_router_identity_and_free_billing_boundary_persist_with_comparison(
    seeded_url: str,
    platform: Platform,
    cost: int | None,
    expected: str,
) -> None:
    settings = Settings(
        database_url=SecretStr(seeded_url),
        llm_provider=LlmProvider.OPENROUTER,
        llm_model="openrouter/free",
        llm_api_key=SecretStr("test-only"),
    )

    async def respond(request: httpx2.Request) -> httpx2.Response:
        assert json.loads(request.content)["provider"]["max_price"]["prompt"] == 0
        return httpx2.Response(
            200,
            json={
                "model": "vendor/example:free",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": reply(model="untrusted/model-identity"),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 400, "completion_tokens": 160, "cost": cost},
            },
        )

    factory = create_session_factory(platform.engine)
    provider = OpenRouterProvider(settings, httpx2.MockTransport(respond))
    app = create_app(settings)
    app.state.diagnostics = DiagnosticsService(
        factory,
        FixedClock(datetime.now(UTC)),
        lambda: platform.simulation.clock().platform_time,
        TopologyService(factory),
        DiagnosticRuntime(settings, provider),
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        sign_in(client, seeded_url)
        incident = client.get("/api/v1/incidents").json()["items"][0]
        path = f"/api/v1/incidents/{incident['id']}"
        response = client.post(
            f"{path}/diagnose?mode=llm", json={}, headers={"Idempotency-Key": "free-router"}
        )
        assert response.status_code == 201, response.text
        result = response.json()
        assert result["status"] == expected
        assert result["provider"] == "openrouter"
        assert result["deterministic_id"] is not None
        if cost == 0:
            assert result["model"] == "openrouter/vendor/example:free"
            assert result["observed_facts"]
            assert result["error_code"] is None
        else:
            assert result["error_code"] == "LLM_INVALID_RESPONSE"
            assert result["observed_facts"] == []
        listed = client.get(f"{path}/diagnostics").json()["items"]
        assert any(item["id"] == result["deterministic_id"] for item in listed)
        (stored,) = platform.rows(
            "SELECT model, prompt_redacted FROM diagnostic WHERE id = :id", id=result["id"]
        )
        assert stored[0] == result["model"]
        assert "test-only" not in stored[1]
        assert client.get("/api/v1/platforms").status_code == 200
