"""Create local demo credentials without printing secrets or replacing configured values."""

import argparse
import os
import re
import secrets
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYS = tuple(f"IPHI_DEMO_{role}_PASSWORD" for role in ("VIEWER", "ENGINEER", "ADMIN"))


def initialize(path: Path) -> None:
    if path.is_symlink():
        raise SystemExit("Refusing to replace a symlinked environment file.")
    content = path.read_text() if path.exists() else (ROOT / ".env.example").read_text()
    updated = content
    for key in KEYS:
        pattern = re.compile(rf"^{key}=(.*)$", re.MULTILINE)
        match = pattern.search(updated)
        if match is not None and match[1].strip().strip("\"'"):
            continue
        line = f"{key}={secrets.token_urlsafe(24)}"
        updated = pattern.sub(line, updated) if match else updated.rstrip() + "\n" + line + "\n"
    if updated != content or not path.exists():
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, prefix=".iphi-env-", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(updated)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    path.chmod(0o600)
    print(  # noqa: T201 - CLI status deliberately excludes credential values.
        f"Demo users viewer/engineer/admin configured in {path.name} (mode 600); "
        "values are not printed."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=ROOT / ".env")
    initialize(parser.parse_args().file)
