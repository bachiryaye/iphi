from enum import StrEnum
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_SEED = 2**31 - 1


class LlmProvider(StrEnum):
    NONE = "none"


class Settings(BaseSettings):
    """Process configuration, read from `IPHI_*` environment variables (Twelve-Factor, S-13)."""

    model_config = SettingsConfigDict(env_prefix="IPHI_", extra="ignore", frozen=True)

    database_url: SecretStr
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    log_format: Literal["json", "console"] = "json"
    cycle_interval_s: float = Field(default=5.0, gt=0, le=60)
    llm_provider: LlmProvider = LlmProvider.NONE
    dev_mutations: bool = Field(
        default=False,
        description="Enables unauthenticated mutations before US-11; honoured on loopback only.",
    )
    bind_host: str = Field(
        default="127.0.0.1",
        max_length=255,
        description="Host address the API and frontend ports are published on (ADR 0007).",
    )
    sim_seed: int = Field(default=42, ge=0, le=MAX_SEED)
