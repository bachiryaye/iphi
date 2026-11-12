import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
# D-13: business timestamps come from the platform clock; only these adapters read real time.
WALL_CLOCK_ADAPTERS = {APP / "core" / "clock.py"}
WALL_CLOCK_CALL = re.compile(r"\b(datetime\.now|datetime\.utcnow|time\.time)\(")


def test_only_the_clock_adapter_reads_wall_time() -> None:
    offenders = [
        str(path.relative_to(APP))
        for path in APP.rglob("*.py")
        if path not in WALL_CLOCK_ADAPTERS and WALL_CLOCK_CALL.search(path.read_text())
    ]

    assert offenders == []
