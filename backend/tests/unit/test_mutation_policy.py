import pytest

from app.identity.domain import MutationPolicy, MutationsDisabledError


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1"])
def test_dev_mutations_on_loopback_are_enabled(host: str) -> None:
    MutationPolicy.evaluate(dev_mutations=True, bind_host=host).enforce()


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "::", "localhost", "example.org"])  # noqa: S104
def test_dev_mutations_published_beyond_loopback_are_refused(host: str) -> None:
    policy = MutationPolicy.evaluate(dev_mutations=True, bind_host=host)

    assert not policy.enabled
    with pytest.raises(MutationsDisabledError, match=host):
        policy.enforce()


def test_mutations_are_disabled_by_default() -> None:
    policy = MutationPolicy.evaluate(dev_mutations=False, bind_host="127.0.0.1")

    with pytest.raises(MutationsDisabledError, match="IPHI_DEV_MUTATIONS"):
        policy.enforce()
