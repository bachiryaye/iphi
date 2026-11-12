"""Write the OpenAPI document consumed by the generated frontend client (rules.md C-21)."""

import json
import sys
from pathlib import Path

from pydantic import SecretStr

from app.core.settings import Settings
from app.main import create_app


def main() -> None:
    target = Path(sys.argv[1])
    # The schema does not depend on the database; the engine is created but never connected.
    settings = Settings(database_url=SecretStr("postgresql+psycopg://openapi@localhost/unused"))
    document = create_app(settings).openapi()
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
