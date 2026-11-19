import asyncio
import time
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

from app.api.auth import auth_service
from app.core.events import Notice, NoticeType
from app.identity.auth_domain import AuthenticationRequiredError
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
    request: Request,
    subscription: Annotated[
        tuple[asyncio.Queue[Notice | None], Notice],
        Depends(event_subscription, scope="request"),
    ],
) -> AsyncIterator[ServerSentEvent]:
    queue, sync = subscription
    yield ServerSentEvent(event=sync.type.value, data=_out(sync), retry=1000)
    checked = time.monotonic()
    while True:
        try:
            notice = await asyncio.wait_for(queue.get(), timeout=15)
        except TimeoutError:
            notice = sync
        if time.monotonic() - checked >= 15:
            try:
                await asyncio.to_thread(
                    auth_service(request).resolve, request.cookies.get("iphi_session")
                )
            except AuthenticationRequiredError:
                return
            checked = time.monotonic()
        if notice is None:
            return
        if notice is not sync:
            yield ServerSentEvent(event=notice.type.value, data=_out(notice))


def _out(notice: Notice) -> StreamEventOut:
    return StreamEventOut(type=notice.type, id=notice.id, platform_time=notice.platform_time)
