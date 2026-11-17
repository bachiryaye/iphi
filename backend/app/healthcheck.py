"""Backend image healthcheck: worker liveness file if present, else GET /health (ADR 0020)."""

import sys
import urllib.request
from pathlib import Path

from app.core.clock import WallClock
from app.core.liveness import age_seconds
from app.core.settings import Settings

TIMEOUT_S = 2.0


def healthy(settings: Settings) -> bool:
    age = age_seconds(Path(settings.liveness_file), WallClock())
    if age is not None:
        return age <= settings.liveness_max_age_s
    url = f"http://127.0.0.1:{settings.port}/health"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
            return bool(response.status == 200)
    except OSError:
        return False


def main() -> int:
    return 0 if healthy(Settings()) else 1


if __name__ == "__main__":
    sys.exit(main())
