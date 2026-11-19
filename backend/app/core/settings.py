import ipaddress
from enum import StrEnum
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_SEED = 2**31 - 1


class LlmProvider(StrEnum):
    NONE = "none"
    FAKE = "fake"
    OPENAI = "openai"
    OPENROUTER = "openrouter"


class Settings(BaseSettings):
    """Process configuration, read from `IPHI_*` environment variables (Twelve-Factor, S-13)."""

    model_config = SettingsConfigDict(env_prefix="IPHI_", extra="ignore", frozen=True)

    database_url: SecretStr
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    log_format: Literal["json", "console"] = "json"
    cycle_interval_s: float = Field(default=5.0, gt=0, le=60)
    llm_provider: LlmProvider = LlmProvider.NONE
    llm_model: str = Field(default="", max_length=89, pattern=r"^[a-zA-Z0-9._:/-]*$")
    llm_reasoning_effort: Literal["default", "none", "minimal", "low", "medium", "high"] = "default"
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_s: float = Field(default=20, gt=0, le=20)
    llm_input_tokens: int = Field(default=8192, ge=2048, le=24_000)
    llm_output_tokens: int = Field(default=1600, ge=256, le=2048)
    deployment_mode: Literal["local", "production"] = "local"
    demo_viewer_password: SecretStr = SecretStr("")
    demo_engineer_password: SecretStr = SecretStr("")
    demo_admin_password: SecretStr = SecretStr("")
    bind_host: str = Field(
        default="127.0.0.1",
        max_length=255,
        description="Host address the API and frontend ports are published on (ADR 0007).",
    )
    allowed_hosts: str = Field(
        default="127.0.0.1,localhost",
        max_length=1024,
        description="Comma-separated Host header values the API answers (DNS rebinding).",
    )
    sim_seed: int = Field(default=42, ge=0, le=MAX_SEED)
    retention_days: int = Field(
        default=7, ge=1, le=90, description="Observation retention in platform days (ADR 0008)."
    )
    port: int = Field(default=8000, ge=1, le=65535, description="Port the API listens on.")
    liveness_file: str = Field(
        default="/tmp/iphi-worker.alive",  # noqa: S108 - per-container tmpfs, not shared
        max_length=4096,
        description="File the worker touches every cycle for the container healthcheck.",
    )
    liveness_max_age_s: float = Field(
        default=300.0,
        gt=0,
        description="Liveness file age beyond which the worker is stuck; above a slow cycle.",
    )
    db_wait_s: float = Field(
        default=60.0,
        ge=0,
        le=600,
        description="How long the bootstrap waits for the database to accept connections.",
    )

    @model_validator(mode="after")
    def local_cookie_boundary(self) -> Settings:
        if self.deployment_mode == "local":
            try:
                loopback = ipaddress.ip_address(self.bind_host).is_loopback
            except ValueError:
                loopback = False
            if not loopback:
                raise ValueError(
                    "Local HTTP sessions require loopback binding; "
                    "use production mode with HTTPS otherwise."
                )
        return self

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]
