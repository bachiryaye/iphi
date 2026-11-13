import os
import uuid
from collections.abc import Callable, Iterator

import pytest
from alembic import command
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import bootstrap
from app.core.db import create_session_factory
from app.core.migrations import alembic_config
from app.core.settings import Settings

pytestmark = pytest.mark.integration


def _admin_url() -> str:
    url = os.environ.get("IPHI_TEST_DATABASE_URL")
    if not url:
        # Integration tests run against real PostgreSQL only (rules.md T-02); never skip silently.
        raise pytest.UsageError(
            "IPHI_TEST_DATABASE_URL is not set; start the db service (make db) or run tests/unit."
        )
    return url


@pytest.fixture
def database_factory() -> Iterator[Callable[[], str]]:
    """Creates fresh, empty databases on demand; all are dropped after the test."""
    admin = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    names: list[str] = []

    def create() -> str:
        name = f"iphi_test_{uuid.uuid4().hex[:12]}"
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        names.append(name)
        return make_url(_admin_url()).set(database=name).render_as_string(hide_password=False)

    try:
        yield create
    finally:
        with admin.connect() as connection:
            for name in names:
                connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def empty_database_url(database_factory: Callable[[], str]) -> str:
    """A fresh, empty database per test, dropped afterwards."""
    return database_factory()


@pytest.fixture
def database_url(empty_database_url: str) -> str:
    command.upgrade(alembic_config(empty_database_url), "head")
    return empty_database_url


@pytest.fixture
def seeded_url(empty_database_url: str) -> str:
    """A migrated and seeded database, as the `migrate` service leaves it."""
    bootstrap(Settings(database_url=SecretStr(empty_database_url)))
    return empty_database_url


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    db_engine = create_engine(database_url)
    yield db_engine
    db_engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)
