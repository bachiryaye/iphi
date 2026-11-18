"""One LISTEN connection per API process; bounded subscribers resynchronize after loss."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from http import HTTPStatus

import psycopg
import structlog
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.events import CHANNEL, Notice, NoticeType
from app.core.exceptions import IphiError

MAX_SUBSCRIBERS = 32
QUEUE_SIZE = 64
HEARTBEAT_SECONDS = 15
RECONNECT_SECONDS = 1

log = structlog.get_logger(__name__)


class StreamUnavailableError(IphiError):
    status = HTTPStatus.SERVICE_UNAVAILABLE
    code = "LIVE_UPDATES_UNAVAILABLE"


class StreamCapacityError(IphiError):
    status = HTTPStatus.SERVICE_UNAVAILABLE
    code = "LIVE_UPDATES_CAPACITY"


class EventHub:
    def __init__(self, database_url: str, platform_now: Callable[[], datetime]) -> None:
        self._conninfo = (
            make_url(database_url)
            .set(drivername="postgresql")
            .render_as_string(hide_password=False)
        )
        self._platform_now = platform_now
        self._subscribers: set[asyncio.Queue[Notice | None]] = set()
        self._closing: set[asyncio.Queue[Notice | None]] = set()
        self.ready = asyncio.Event()

    @asynccontextmanager
    async def running(self) -> AsyncIterator[None]:
        listener = asyncio.create_task(self._listen(), name="iphi-listen")
        heartbeat = asyncio.create_task(self._heartbeat(), name="iphi-sse-heartbeat")
        try:
            yield
        finally:
            listener.cancel()
            heartbeat.cancel()
            for task in (listener, heartbeat):
                with suppress(asyncio.CancelledError):
                    await task
            self._disconnect()

    def subscribe(self) -> asyncio.Queue[Notice | None]:
        if not self.ready.is_set():
            raise StreamUnavailableError(
                "Live updates are reconnecting. Polling remains available."
            )
        if len(self._subscribers) >= MAX_SUBSCRIBERS:
            raise StreamCapacityError(
                "Too many live streams. Close an unused tab or retry shortly."
            )
        queue: asyncio.Queue[Notice | None] = asyncio.Queue(QUEUE_SIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Notice | None]) -> None:
        self._subscribers.discard(queue)
        self._closing.discard(queue)

    async def sync(self) -> Notice:
        try:
            at = await asyncio.to_thread(self._platform_now)
        except (SQLAlchemyError, IphiError) as exc:
            raise StreamUnavailableError(
                "The platform clock is unavailable. Retry shortly."
            ) from exc
        return Notice(NoticeType.SYNC, "stream", at)

    async def _listen(self) -> None:
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    self._conninfo,
                    autocommit=True,
                    connect_timeout=3,
                    application_name="iphi-events",
                ) as connection:
                    await connection.execute(f"LISTEN {CHANNEL}")
                    self.ready.set()
                    log.info("events.listener_connected")
                    async for item in connection.notifies():
                        try:
                            notice = Notice.decode(item.payload)
                        except ValueError, TypeError:
                            log.warning("events.notice_rejected")
                        else:
                            self._broadcast(notice)
            except psycopg.Error as exc:
                log.warning("events.listener_unavailable", error=type(exc).__name__)
            finally:
                self._disconnect()
            await asyncio.sleep(RECONNECT_SECONDS)

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            if self.ready.is_set():
                try:
                    sync = await self.sync()
                except StreamUnavailableError:
                    log.warning("events.clock_unavailable")
                    self._drop_subscribers()
                else:
                    self._broadcast(Notice(NoticeType.HEARTBEAT, "stream", sync.platform_time))

    def _broadcast(self, notice: Notice) -> None:
        for queue in tuple(self._subscribers - self._closing):
            try:
                queue.put_nowait(notice)
            except asyncio.QueueFull:
                close_queue(queue)
                self._closing.add(queue)
                log.warning("events.client_overflow")

    def _disconnect(self) -> None:
        self.ready.clear()
        self._drop_subscribers()

    def _drop_subscribers(self) -> None:
        for queue in self._subscribers:
            close_queue(queue)
        # A closing HTTP response still occupies its slot until request teardown.
        self._closing.update(self._subscribers)


def close_queue(queue: asyncio.Queue[Notice | None]) -> None:
    while not queue.empty():
        queue.get_nowait()
    queue.put_nowait(None)
