import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.liveness import LivenessFile, age_seconds
from app.core.settings import Settings
from app.healthcheck import healthy
from tests.fakes import FixedClock

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _settings(path: Path, max_age_s: float = 300) -> Settings:
    return Settings(
        database_url=SecretStr("postgresql+psycopg://unused@127.0.0.1:1/unused"),
        liveness_file=str(path),
        liveness_max_age_s=max_age_s,
        port=1,
    )


def test_age_is_none_without_file(tmp_path: Path) -> None:
    assert age_seconds(tmp_path / "missing", FixedClock(NOW)) is None


def test_age_counts_from_the_last_touch(tmp_path: Path) -> None:
    path = tmp_path / "alive"
    LivenessFile(path).touch()
    os.utime(path, (NOW.timestamp() - 42, NOW.timestamp() - 42))

    assert age_seconds(path, FixedClock(NOW)) == pytest.approx(42)


def test_touch_failure_does_not_raise(tmp_path: Path) -> None:
    LivenessFile(tmp_path / "missing-dir" / "alive").touch()


def test_worker_is_healthy_while_its_file_is_fresh(tmp_path: Path) -> None:
    path = tmp_path / "alive"
    LivenessFile(path).touch()

    assert healthy(_settings(path))


def test_worker_with_a_stale_file_is_unhealthy(tmp_path: Path) -> None:
    path = tmp_path / "alive"
    LivenessFile(path).touch()
    old = path.stat().st_mtime - 301
    os.utime(path, (old, old))

    assert not healthy(_settings(path))


def test_without_file_the_api_must_answer(tmp_path: Path) -> None:
    assert not healthy(_settings(tmp_path / "missing"))
