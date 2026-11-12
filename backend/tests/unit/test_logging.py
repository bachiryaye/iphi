import uuid
from datetime import UTC, datetime

from app.core.logging import wire_values


def test_logged_datetimes_and_ids_render_as_wire_strings() -> None:
    at = datetime(2026, 11, 12, 10, 42, 7, tzinfo=UTC)
    run_id = uuid.UUID(int=1)

    rendered = wire_values(None, "info", {"event": "x", "at": at, "run": run_id, "n": 3})

    assert rendered == {"event": "x", "at": "2026-11-12T10:42:07+00:00", "run": str(run_id), "n": 3}
