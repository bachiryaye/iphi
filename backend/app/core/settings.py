from enum import StrEnum
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
