import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app.core.migrations import alembic_config, expected_head
from app.schema import metadata

pytestmark = pytest.mark.integration

APPLICATION_TABLES = {"platform", "monitor_heartbeat", "audit_event"}


def application_tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


def test_upgrade_creates_initial_schema(database_url: str) -> None:
    assert application_tables(database_url) == APPLICATION_TABLES


def test_downgrade_to_base_and_upgrade_again_is_clean(database_url: str) -> None:
    config = alembic_config(database_url)

    command.downgrade(config, "base")
    assert application_tables(database_url) == set()

    command.upgrade(config, "head")
    assert application_tables(database_url) == APPLICATION_TABLES


def test_orm_metadata_matches_migrations(engine: Engine) -> None:
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "compare_server_default": True}
        )
        assert compare_metadata(context, metadata) == []


def test_database_revision_is_code_head(engine: Engine) -> None:
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()

    assert revision == expected_head()


@pytest.fixture
def audit_row(engine: Engine) -> Engine:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO audit_event (id, occurred_at, actor_label, action, outcome) "
                "VALUES (gen_random_uuid(), now(), 'dev-local', 'scenario.start', 'allowed')"
            )
        )
    return engine


@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit_event SET outcome = 'denied'", "DELETE FROM audit_event"],
)
def test_audit_log_is_append_only(audit_row: Engine, statement: str) -> None:
    with pytest.raises(DBAPIError, match="append-only"), audit_row.begin() as connection:
        connection.execute(text(statement))


def test_platform_environment_is_restricted_to_simulation(engine: Engine) -> None:
    with pytest.raises(DBAPIError, match="ck_platform_environment_v1"), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO platform (id, key, name, environment) "
                "VALUES (gen_random_uuid(), 'plant', 'Plant', 'production')"
            )
        )
