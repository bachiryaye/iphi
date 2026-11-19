import asyncio
import json
import socket
import threading
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx2
import psycopg
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.db import create_session_factory
from app.core.events import CHANNEL, Notice, NoticeType, notify
from app.core.settings import Settings
from app.main import create_app
from app.monitor.events import MAX_SUBSCRIBERS, EventHub, StreamCapacityError
from tests.api_client import sign_in

pytestmark = pytest.mark.integration
AT = datetime(2026, 11, 18, tzinfo=UTC)


def conninfo(url: str) -> str:
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


def test_postgresql_delivers_only_committed_changes(seeded_url: str) -> None:
    engine = create_engine(seeded_url)
    factory = create_session_factory(engine)
    with psycopg.connect(conninfo(seeded_url), autocommit=True) as listener:
        listener.execute(f"LISTEN {CHANNEL}")
        with factory() as session:
            notify(session, Notice(NoticeType.COMPONENT, "rolled-back", AT))
            session.rollback()
        with factory.begin() as session:
            notify(session, Notice(NoticeType.COMPONENT, "committed", AT))
        messages = list(listener.notifies(timeout=5, stop_after=1))
        assert [Notice.decode(message.payload).id for message in messages] == ["committed"]
    engine.dispose()


def test_listener_fanout_capacity_and_reconnection_use_the_same_database(seeded_url: str) -> None:
    engine = create_engine(seeded_url)
    factory = create_session_factory(engine)

    def send(entity: str) -> None:
        with factory.begin() as session:
            notify(session, Notice(NoticeType.INCIDENT_OPENED, entity, AT))

    def disconnect() -> None:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=current_database() AND application_name='iphi-events'"
                )
            )

    async def exercise() -> None:
        hub = EventHub(seeded_url, lambda: AT)
        async with hub.running():
            await asyncio.wait_for(hub.ready.wait(), 5)
            queues = [hub.subscribe() for _ in range(MAX_SUBSCRIBERS)]
            with pytest.raises(StreamCapacityError):
                hub.subscribe()
            await asyncio.to_thread(send, "first")
            for queue in queues:
                notice = await asyncio.wait_for(queue.get(), 5)
                assert notice is not None
                assert notice.id == "first"
            await asyncio.to_thread(disconnect)
            assert await asyncio.wait_for(queues[0].get(), 5) is None
            for queue in queues:
                hub.unsubscribe(queue)
            await asyncio.wait_for(hub.ready.wait(), 5)
            queue = hub.subscribe()
            assert (await hub.sync()).type is NoticeType.SYNC
            await asyncio.to_thread(send, "after-reconnect")
            notice = await asyncio.wait_for(queue.get(), 5)
            assert notice is not None
            assert notice.id == "after-reconnect"
            hub.unsubscribe(queue)

    asyncio.run(exercise())
    engine.dispose()


@pytest.fixture
def stream_server(seeded_url: str) -> Iterator[tuple[str, str]]:
    app = create_app(Settings(database_url=SecretStr(seeded_url)))
    auth_client = TestClient(app, base_url="http://127.0.0.1")
    sign_in(auth_client, seeded_url, "viewer")
    session_cookie = "iphi_session=" + auth_client.cookies["iphi_session"]
    original = app.router.lifespan_context
    started = threading.Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with original(app):
            await asyncio.wait_for(app.state.events.ready.wait(), 5)
            started.set()
            yield

    app.router.lifespan_context = lifespan
    with socket.socket() as listening:
        listening.bind(("127.0.0.1", 0))
        listening.listen()
        port = listening.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning", log_config=None))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listening]}, daemon=True)
        thread.start()
        try:
            assert started.wait(10), "The test API did not start."
            yield f"http://127.0.0.1:{port}", session_cookie
        finally:
            server.should_exit = True
            thread.join(10)
            assert not thread.is_alive(), "The test API did not stop."


def test_http_stream_flushes_sync_and_committed_notices(
    stream_server: tuple[str, str], seeded_url: str
) -> None:
    engine = create_engine(seeded_url)
    factory = create_session_factory(engine)
    with (
        httpx2.Client(timeout=5, headers={"cookie": stream_server[1]}) as client,
        client.stream("GET", stream_server[0] + "/api/v1/events/stream") as response,
    ):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-accel-buffering"] == "no"
        lines = response.iter_lines()
        first = next(line for line in lines if line.startswith("data: "))
        assert json.loads(first.removeprefix("data: "))["type"] == "sync"
        with factory.begin() as session:
            notify(session, Notice(NoticeType.COMPONENT, "confirmed-component", AT))
        following = next(line for line in lines if line.startswith("data: "))
        assert Notice.decode(following.removeprefix("data: ")).id == "confirmed-component"
        with factory.begin() as session:
            notify(session, Notice(NoticeType.COMPONENT, "a\n\nevent: command", AT))
        following = next(line for line in lines if line.startswith("data: "))
        assert Notice.decode(following.removeprefix("data: ")).id == "a\n\nevent: command"
    engine.dispose()
