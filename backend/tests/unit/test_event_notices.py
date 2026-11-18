import asyncio
import json
from datetime import UTC, datetime

import pytest

from app.core.events import Notice, NoticeType
from app.monitor.events import close_queue

AT = datetime(2026, 11, 18, tzinfo=UTC)


def test_notice_roundtrip_preserves_entity_time_and_simulation_marker() -> None:
    notice = Notice(NoticeType.COMPONENT, "component-1", AT)
    assert Notice.decode(notice.encode()) == notice
    assert json.loads(notice.encode())["environment"] == "simulation"


@pytest.mark.parametrize(
    "value",
    [
        "invalid",
        "[]",
        "{}",
        " " * 1025,
        json.dumps(
            {
                "type": "command",
                "id": "1",
                "platform_time": AT.isoformat(),
                "environment": "simulation",
            }
        ),
        json.dumps(
            {
                "type": "heartbeat",
                "id": "1",
                "platform_time": "2026-11-18T00:00:00",
                "environment": "simulation",
            }
        ),
        json.dumps(
            {
                "type": "heartbeat",
                "id": "1",
                "platform_time": AT.isoformat(),
                "environment": "production",
            }
        ),
    ],
)
def test_invalid_notice_is_refused_before_fanout(value: str) -> None:
    with pytest.raises(ValueError, match=r"Expecting|notice|Notice|UTC|simulation"):
        Notice.decode(value)


def test_entity_text_cannot_inject_sse_fields() -> None:
    encoded = Notice(NoticeType.COMPONENT, "a\n\nevent: command", AT).encode()
    assert len(encoded.splitlines()) == 1
    assert json.loads(encoded)["id"] == "a\n\nevent: command"


def test_closing_a_full_queue_discards_stale_notices_and_delivers_disconnect() -> None:
    queue: asyncio.Queue[Notice | None] = asyncio.Queue(2)
    for _ in range(2):
        queue.put_nowait(Notice(NoticeType.HEARTBEAT, "stream", AT))
    close_queue(queue)
    assert queue.get_nowait() is None
    assert queue.empty()
