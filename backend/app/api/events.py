import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

from app.core.events import Notice, NoticeType
from app.monitor.events import EventHub

router = APIRouter(prefix="/api/v1/events", tags=["events"])


class StreamEventOut(BaseModel):
    type: NoticeType
    id: str = Field(min_length=1, max_length=64)
    platform_time: datetime
    environment: Literal["simulation"] = "simulation"


def event_hub(request: Request) -> EventHub:
    hub: EventHub = request.app.state.events
    return hub


async def event_subscription(
    hub: Annotated[EventHub, Depends(event_hub)],
) -> AsyncIterator[tuple[asyncio.Queue[Notice | None], Notice]]:
    queue = hub.subscribe()
    try:
        yield queue, await hub.sync()
    finally:
        hub.unsubscribe(queue)


@router.get(
    "/stream",
    summary="Live change notices; always resynchronize on connection.",
    response_class=EventSourceResponse,
    responses={
        200: {"model": StreamEventOut, "description": "Each SSE data field follows this envelope."},
        503: {
            "description": "LIVE_UPDATES_UNAVAILABLE or LIVE_UPDATES_CAPACITY; use polling.",
            "content": {
                "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
            },
        },
        "default": {
            "description": "RFC 9457 errors before streaming begins.",
            "content": {
                "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
            },
        },
    },
)
async def events_stream(
    subscription: Annotated[
        tuple[asyncio.Queue[Notice | None], Notice],
        Depends(event_subscription, scope="request"),
    ],
) -> AsyncIterator[ServerSentEvent]:
    queue, sync = subscription
    yield ServerSentEvent(event=sync.type.value, data=_out(sync), retry=1000)
    while (notice := await queue.get()) is not None:
        yield ServerSentEvent(event=notice.type.value, data=_out(notice))


def _out(notice: Notice) -> StreamEventOut:
    return StreamEventOut(type=notice.type, id=notice.id, platform_time=notice.platform_time)
