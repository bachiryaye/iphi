import asyncio
import json

import httpx2
import pytest
from pydantic import SecretStr

from app.core.settings import LlmProvider, Settings
from app.diagnostics.evidence import build_pack
from app.diagnostics.providers import (
    MAX_ENVELOPE_BYTES,
    OpenRouterProvider,
    ProviderError,
    bounded_call,
    build_provider,
)
from tests.unit.test_deterministic_diagnosis import collector_input
from tests.unit.test_llm_diagnosis import reply


def settings(model: str = "openrouter/free") -> Settings:
    return Settings(
        database_url=SecretStr("unused"),
        llm_provider=LlmProvider.OPENROUTER,
        llm_model=model,
        llm_api_key=SecretStr("test-only"),
    )


def envelope() -> dict[str, object]:
    return {
        "model": "vendor/example:free",
        "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": reply()}}
        ],
        "usage": {"prompt_tokens": 400, "completion_tokens": 160, "cost": 0},
    }


def test_free_request_has_a_zero_price_ceiling_and_keeps_upstream_model_identity() -> None:
    captured: list[httpx2.Request] = []

    async def respond(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return httpx2.Response(200, json=envelope())

    provider = OpenRouterProvider(settings(), httpx2.MockTransport(respond))
    result = asyncio.run(bounded_call(provider, build_pack(collector_input(), 8192), 20))
    request = captured[0]
    payload = json.loads(request.content)
    assert request.url == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer test-only"
    assert payload["model"] == "openrouter/free"
    assert payload["provider"] == {
        "require_parameters": True,
        "max_price": {"prompt": 0, "completion": 0, "request": 0, "image": 0},
    }
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["plugins"] == []
    assert "reasoning" not in payload
    assert "models" not in payload
    assert "tools" not in payload
    assert "test-only" not in request.content.decode()
    assert result.resolved_model == "openrouter/vendor/example:free"
    assert (result.input_tokens, result.output_tokens) == (400, 160)
    assert isinstance(build_provider(settings()), OpenRouterProvider)


@pytest.mark.parametrize(
    "model",
    ["openrouter/auto", "openai/paid", "vendor/name", "https://example.invalid/name:free", "free"],
)
def test_nonfree_or_url_models_are_refused_before_any_network_call(model: str) -> None:
    async def forbidden(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("A disallowed model must not reach the network.")

    provider = OpenRouterProvider(settings(model), httpx2.MockTransport(forbidden))
    with pytest.raises(ProviderError, match="LLM_FREE_MODEL_REQUIRED"):
        asyncio.run(provider.generate(build_pack(collector_input(), 8192)))


@pytest.mark.parametrize("model", ["openrouter/free", "vendor/example:free"])
def test_explicit_free_variants_are_accepted(model: str) -> None:
    async def respond(request: httpx2.Request) -> httpx2.Response:
        assert json.loads(request.content)["model"] == model
        return httpx2.Response(200, json=envelope())

    provider = OpenRouterProvider(settings(model), httpx2.MockTransport(respond))
    assert asyncio.run(provider.generate(build_pack(collector_input(), 8192))).text


@pytest.mark.parametrize(
    "usage",
    [
        {"prompt_tokens": 400, "completion_tokens": 160, "cost": 0.01},
        {"prompt_tokens": 400, "completion_tokens": 160},
        {"prompt_tokens": 400, "completion_tokens": 160, "cost": -1},
        {"prompt_tokens": 400, "completion_tokens": 160, "cost": "0"},
    ],
)
def test_nonzero_unknown_or_invalid_billing_is_rejected(usage: dict[str, object]) -> None:
    async def respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={**envelope(), "usage": usage})

    provider = OpenRouterProvider(settings(), httpx2.MockTransport(respond))
    with pytest.raises(ProviderError, match="LLM_INVALID_RESPONSE"):
        asyncio.run(provider.generate(build_pack(collector_input(), 8192)))


@pytest.mark.parametrize(("status", "attempts"), [(302, 1), (401, 1), (429, 1), (503, 2)])
def test_no_redirect_or_paid_fallback_and_bounded_transient_retry(
    status: int, attempts: int
) -> None:
    calls = 0

    async def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        assert str(request.url).startswith("https://openrouter.ai/")
        return httpx2.Response(status, headers={"Location": "https://example.invalid/paid"})

    provider = OpenRouterProvider(settings(), httpx2.MockTransport(respond))
    with pytest.raises(ProviderError, match="LLM_HTTP_ERROR"):
        asyncio.run(bounded_call(provider, build_pack(collector_input(), 8192), 20))
    assert calls == attempts


@pytest.mark.parametrize(
    ("data", "code"),
    [
        ({**envelope(), "choices": []}, "LLM_INVALID_RESPONSE"),
        (
            {
                **envelope(),
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"role": "assistant", "content": reply()},
                    }
                ],
            },
            "LLM_INCOMPLETE",
        ),
        (
            {**envelope(), "usage": {"prompt_tokens": 400, "completion_tokens": 1601, "cost": 0}},
            "LLM_TOKEN_BUDGET",
        ),
    ],
)
def test_incomplete_or_over_budget_answers_are_not_diagnoses(
    data: dict[str, object], code: str
) -> None:
    async def respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=data)

    provider = OpenRouterProvider(settings(), httpx2.MockTransport(respond))
    with pytest.raises(ProviderError, match=code):
        asyncio.run(provider.generate(build_pack(collector_input(), 8192)))


def test_oversized_envelope_is_stopped_before_parsing() -> None:
    async def respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"x" * (MAX_ENVELOPE_BYTES + 1))

    provider = OpenRouterProvider(settings(), httpx2.MockTransport(respond))
    with pytest.raises(ProviderError, match="LLM_RESPONSE_TOO_LARGE"):
        asyncio.run(provider.generate(build_pack(collector_input(), 8192)))


@pytest.mark.parametrize("effort", ["none", "minimal", "low", "medium", "high"])
def test_explicit_reasoning_effort_is_sent_without_changing_the_budget(effort: str) -> None:
    configured = Settings.model_validate(
        {**settings("particle-ai/particle-1:free").model_dump(), "llm_reasoning_effort": effort}
    )

    async def respond(request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        assert payload["reasoning"] == {"effort": effort}
        assert payload["max_tokens"] == 1600
        assert payload["provider"]["require_parameters"] is True
        assert payload["provider"]["max_price"]["completion"] == 0
        return httpx2.Response(200, json=envelope())

    provider = OpenRouterProvider(configured, httpx2.MockTransport(respond))
    assert asyncio.run(provider.generate(build_pack(collector_input(), 8192))).text
