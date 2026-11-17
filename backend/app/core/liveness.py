"""Worker liveness file read by the container healthcheck (ADR 0020)."""

from pathlib import Path

import structlog

from app.core.clock import Clock

log = structlog.get_logger(__name__)


class LivenessFile:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._failed = False

    def touch(self) -> None:
        try:
            self._path.touch()
        except OSError as exc:
            # Never stops the worker; the healthcheck reports it instead.
            if not self._failed:
                log.warning("liveness.touch_failed", path=str(self._path), error=str(exc))
            self._failed = True


def age_seconds(path: Path, clock: Clock) -> float | None:
    try:
        modified = path.stat().st_mtime
    except FileNotFoundError:
        return None
    return clock.now().timestamp() - modified
