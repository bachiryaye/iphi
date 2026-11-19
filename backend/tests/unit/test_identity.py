import pytest

from app.identity.passwords import csrf_for, csrf_matches, new_token


def test_csrf_proof_is_bound_to_one_session() -> None:
    first, second = new_token(), new_token()
    assert csrf_matches(first, csrf_for(first))
    assert not csrf_matches(second, csrf_for(first))


@pytest.mark.parametrize("supplied", ["", "0" * 63, "0" * 65, "é" * 64, "💡" * 64])
def test_malformed_csrf_is_rejected_without_an_exception(supplied: str) -> None:
    assert not csrf_matches(new_token(), supplied)
