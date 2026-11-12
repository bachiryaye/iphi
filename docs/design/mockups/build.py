"""Assemble the static mock-ups from src/ partials so pages open directly from disk.

The icon sprite is inlined because browsers block external <use> references on file://.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PAGES = {
    "overview.html": "overview",
    "incident.html": "incidents",
    "component.html": "components",
    "states.html": "",
}

sys.path.insert(0, str(SRC))
import component_chart  # noqa: E402


def render(page: str, section: str) -> str:
    html = (SRC / page).read_text(encoding="utf-8")
    sidebar = (SRC / "_sidebar.html").read_text(encoding="utf-8")
    sidebar = re.sub(
        r"\{\{current:(\w+)\}\}",
        lambda m: 'aria-current="page"' if m.group(1) == section else "",
        sidebar,
    )
    html = html.replace("<!-- @icons -->", (SRC / "_icons.svg").read_text(encoding="utf-8"))
    html = html.replace("<!-- @sidebar -->", sidebar)
    html = html.replace("<!-- @topbar -->", (SRC / "_topbar.html").read_text(encoding="utf-8"))
    html = html.replace(
        "<!-- @component-chart -->",
        component_chart.svg() + f'<script type="application/json" id="hc-data">{component_chart.data()}</script>',
    )
    html = html.replace("<!-- @component-transitions -->", component_chart.transitions_table())
    if "<!-- @" in html:
        raise ValueError(f"unresolved placeholder in {page}")
    return html


if __name__ == "__main__":
    for page, section in PAGES.items():
        if (SRC / page).exists():
            (ROOT / page).write_text(render(page, section), encoding="utf-8")
            print(f"built {page}")
