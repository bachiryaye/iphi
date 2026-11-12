from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(ALEMBIC_INI))
    if database_url is not None:
        # ConfigParser interpolation would otherwise consume '%' in URL-encoded passwords.
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def expected_head() -> str:
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    if head is None:
        raise RuntimeError("no Alembic revision found")
    return head
