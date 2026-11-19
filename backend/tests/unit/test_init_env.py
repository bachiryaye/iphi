import stat
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "init_env.py"


def test_initialization_preserves_configured_credentials_and_protects_generated_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / ".env"
    original = (
        "IPHI_LLM_API_KEY=provider-test-placeholder\n"
        "IPHI_DEMO_ADMIN_PASSWORD=existing-test-placeholder\n"
        "IPHI_DEMO_VIEWER_PASSWORD=\n"
    )
    target.write_text(original)
    result = subprocess.run(  # noqa: S603 - fixed interpreter/script and pytest-owned path
        [sys.executable, str(SCRIPT), "--file", str(target)], capture_output=True, check=True
    )
    content = target.read_text()
    assert "IPHI_LLM_API_KEY=provider-test-placeholder" in content
    assert "IPHI_DEMO_ADMIN_PASSWORD=existing-test-placeholder" in content
    values = dict(line.split("=", 1) for line in content.splitlines())
    assert len(values["IPHI_DEMO_VIEWER_PASSWORD"]) >= 24
    assert len(values["IPHI_DEMO_ENGINEER_PASSWORD"]) >= 24
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert all(value.encode() not in result.stdout + result.stderr for value in values.values())
    subprocess.run(  # noqa: S603 - fixed interpreter/script and pytest-owned path
        [sys.executable, str(SCRIPT), "--file", str(target)], check=True
    )
    assert target.read_text() == content


def test_initialization_refuses_to_replace_a_symlink(tmp_path: Path) -> None:
    original = tmp_path / "owner.env"
    original.write_text("owner configuration")
    link = tmp_path / ".env"
    link.symlink_to(original)
    result = subprocess.run(  # noqa: S603 - fixed interpreter/script and pytest-owned path
        [sys.executable, str(SCRIPT), "--file", str(link)], capture_output=True, check=False
    )
    assert result.returncode != 0
    assert original.read_text() == "owner configuration"
