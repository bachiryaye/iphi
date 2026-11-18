import pytest

from app.reporting.csv import safe_cell
from app.reporting.pdf import report_asset


@pytest.mark.parametrize(
    "value",
    [
        "=SUM(1,2)",
        "+cmd",
        "-1+2",
        "@SUM(A1)",
        "\tvalue",
        "\rvalue",
        "\n=cmd",
        "  =cmd",
        "\ufeff=cmd",
    ],
)
def test_formula_cells_are_quoted_without_discarding_original_text(value: str) -> None:
    assert safe_cell(value) == "'" + value


@pytest.mark.parametrize("value", ["collector-01", "normal = text", "1.5", "", "R-AVAIL-001"])
def test_plain_cells_keep_their_value(value: str) -> None:
    assert safe_cell(value) == value


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/font.ttf",
        "http://127.0.0.1/admin",
        "file:///etc/passwd",
        "data:text/html,secret",
        "iphi-font:../../etc/passwd",
        "iphi-font:regular?other",
    ],
)
def test_pdf_assets_cannot_access_network_files_or_arbitrary_data(url: str) -> None:
    with pytest.raises(ValueError, match="not allowlisted"):
        report_asset(url)
