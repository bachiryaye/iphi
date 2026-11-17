"""Provider adapters. No tools, arbitrary endpoints, credentials in prompts, or SDK retries."""

import asyncio
import json
from dataclasses import dataclass
from typing import Protocol

import httpx2
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from app.core.settings import LlmProvider, Settings
from app.diagnostics.evidence import SYSTEM_PROMPT, EvidencePack
from app.diagnostics.validation import DiagnosisIn

MAX_REPLY_BYTES = 64_000
MAX_ENVELOPE_BYTES = 256_000
OPENAI_URL = "https://api.openai.com/v1/responses"


class ProviderError(Exception):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ProviderReply:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class Provider(Protocol):
    name: str
    model: str

    async def generate(self, pack: EvidencePack) -> ProviderReply: ...


class NoneProvider:
    name = "none"
    model = "none"

    async def generate(self, pack: EvidencePack) -> ProviderReply:
        raise ProviderError("LLM_DISABLED")


class FakeProvider:
    """Local test provider; never interprets log text or makes a network request."""

    name = "fake"
    model = "fake/evidence-v1"

    async def generate(self, pack: EvidencePack) -> ProviderReply:
        labels = list(pack.citations)[:1]
        result = {
            "observed_facts": [
                {
                    "text": "Stored evidence is available for this simulated incident.",
                    "evidence_ids": labels,
                }
            ],
            "hypotheses": [
                {
                    "text": "The stored condition may correlate with downstream impact; "
                    "causation is not proven.",
                    "evidence_ids": labels,
                    "uncertainty": "high",
                }
            ],
            "recommended_checks": [
                {
                    "text": "Compare the cited rule evaluation with its samples.",
                    "evidence_ids": labels,
                }
            ],
            "limitations": ["Local fake provider: test output, no language model was called."],
            "model": self.model,
        }
        text = json.dumps(result)
        return ProviderReply(text)


class _Usage(BaseModel):
    input_tokens: int = Field(ge=0, le=1_000_000)
    output_tokens: int = Field(ge=0, le=1_000_000)


class _Content(BaseModel):
    type: str
    text: str | None = None


class _Output(BaseModel):
    type: str
    content: list[_Content] = []


class _Envelope(BaseModel):
    model_config = ConfigDict(strict=True)
    status: str
    output: list[_Output]
    usage: _Usage


class OpenAIProvider:
    name = "openai"

    def __init__(
        self, settings: Settings, transport: httpx2.AsyncBaseTransport | None = None
    ) -> None:
        self.model = f"openai/{settings.llm_model}" if settings.llm_model else "openai/unconfigured"
        self._model = settings.llm_model
        self._key: SecretStr = settings.llm_api_key
        self._output_tokens = settings.llm_output_tokens
        self._transport = transport

    async def generate(self, pack: EvidencePack) -> ProviderReply:
        key = self._key.get_secret_value()
        if (
            not self._model
            or not key
            or not key.isascii()
            or any(ord(c) <= 32 or ord(c) == 127 for c in key)
        ):
            raise ProviderError("LLM_NOT_CONFIGURED")
        payload = {
            "model": self._model,
            "instructions": SYSTEM_PROMPT,
            "input": pack.prompt,
            "max_output_tokens": self._output_tokens,
            "store": False,
            "tools": [],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "incident_diagnosis",
                    "strict": True,
                    "schema": DiagnosisIn.model_json_schema(),
                }
            },
        }
        try:
            async with (
                httpx2.AsyncClient(
                    follow_redirects=False,
                    trust_env=False,
                    transport=self._transport,
                ) as client,
                client.stream(
                    "POST",
                    OPENAI_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {key}"},
                ) as response,
            ):
                if response.status_code != 200:
                    raise ProviderError("LLM_HTTP_ERROR", retryable=response.status_code >= 500)
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_ENVELOPE_BYTES:
                        raise ProviderError("LLM_RESPONSE_TOO_LARGE")
            envelope = _Envelope.model_validate_json(body)
            if envelope.status != "completed":
                raise ProviderError("LLM_INCOMPLETE")
            text = "".join(
                part.text or ""
                for item in envelope.output
                if item.type == "message"
                for part in item.content
                if part.type == "output_text"
            )
            if not text or len(text.encode()) > MAX_REPLY_BYTES:
                raise ProviderError("LLM_INVALID_RESPONSE")
            if envelope.usage.output_tokens > self._output_tokens:
                raise ProviderError("LLM_TOKEN_BUDGET")
            return ProviderReply(text, envelope.usage.input_tokens, envelope.usage.output_tokens)
        except httpx2.TimeoutException as exc:
            raise ProviderError("LLM_TIMEOUT", retryable=True) from exc
        except httpx2.HTTPError as exc:
            raise ProviderError("LLM_TRANSPORT_ERROR", retryable=True) from exc
        except ValidationError as exc:
            raise ProviderError("LLM_INVALID_RESPONSE") from exc


def build_provider(settings: Settings) -> Provider:
    if settings.llm_provider is LlmProvider.FAKE:
        return FakeProvider()
    if settings.llm_provider is LlmProvider.OPENAI:
        return OpenAIProvider(settings)
    return NoneProvider()


async def bounded_call(provider: Provider, pack: EvidencePack, timeout_s: float) -> ProviderReply:
    try:
        # One deadline covers both attempts, including response streaming (ADR 0006).
        async with asyncio.timeout(timeout_s):
            for attempt in range(2):
                try:
                    result = await provider.generate(pack)
                    if len(result.text.encode()) > MAX_REPLY_BYTES:
                        raise ProviderError("LLM_RESPONSE_TOO_LARGE")
                    return result
                except ProviderError as exc:
                    if not exc.retryable or attempt == 1:
                        raise
    except TimeoutError as exc:
        raise ProviderError("LLM_TIMEOUT") from exc
    raise AssertionError("unreachable")
