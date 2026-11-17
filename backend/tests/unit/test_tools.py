import pytest

from scripts.client import Api, ToolError, wait_until
from scripts.perf import percentile


@pytest.mark.parametrize(
    ("share", "expected"),
    [(0.5, 3.0), (0.95, 5.0), (0.2, 1.0), (1.0, 5.0)],
)
def test_percentile_is_an_observed_value(share: float, expected: float) -> None:
    assert percentile([5.0, 1.0, 3.0, 2.0, 4.0], share) == expected


def test_percentile_of_a_single_value() -> None:
    assert percentile([42.0], 0.95) == 42.0


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://host", "127.0.0.1:8000", "http://"])
def test_api_accepts_http_urls_only(url: str) -> None:
    with pytest.raises(ToolError, match="http"):
        Api(url)


def test_wait_until_returns_the_first_value() -> None:
    answers = iter([None, "seen"])

    assert wait_until("an answer", lambda: next(answers), timeout_s=5, interval_s=0) == "seen"


def test_wait_until_names_the_unmet_expectation() -> None:
    with pytest.raises(ToolError, match="collector-01 critical"):
        wait_until("collector-01 critical", lambda: None, timeout_s=0)
