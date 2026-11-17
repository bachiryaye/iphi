from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.bootstrap import bootstrap, connect_when_ready
from app.core.migrations import expected_head
from app.core.settings import Settings

pytestmark = pytest.mark.integration


def test_concurrent_bootstraps_migrate_once_and_both_succeed(empty_database_url: str) -> None:
    settings = Settings(database_url=SecretStr(empty_database_url))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: bootstrap(settings), range(2)))

    assert outcomes == [None, None]
    engine = create_engine(empty_database_url)
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        platforms = connection.execute(text("SELECT count(*) FROM platform")).scalar()
    engine.dispose()
    assert (revision, platforms) == (expected_head(), 1)


def test_database_wait_gives_up_after_its_budget() -> None:
    engine = create_engine("postgresql+psycopg://iphi@127.0.0.1:1/none")

    with pytest.raises(OperationalError):
        connect_when_ready(engine, wait_s=0)
    engine.dispose()
