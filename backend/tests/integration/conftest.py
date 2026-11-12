import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import create_session_factory
from app.core.migrations import alembic_config

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
def empty_database_url() -> Iterator[str]:
    """A fresh, empty database per test, dropped afterwards."""
    admin = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    name = f"iphi_test_{uuid.uuid4().hex[:12]}"
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield make_url(_admin_url()).set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def database_url(empty_database_url: str) -> str:
    command.upgrade(alembic_config(empty_database_url), "head")
    return empty_database_url


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    db_engine = create_engine(database_url)
    yield db_engine
    db_engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)
