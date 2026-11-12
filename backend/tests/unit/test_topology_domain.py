import pytest

from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.topology.domain import (
    ComponentSpec,
    ComponentType,
    Criticality,
    DependencyKind,
    DependencySpec,
    TopologyError,
    TopologySpec,
    downstream_of,
)

FLOW = DependencyKind.DATA_FLOW


def spec(*edges: tuple[str, str]) -> TopologySpec:
    keys = sorted({k for edge in edges for k in edge} | {"a"})
    return TopologySpec(
        "p",
        "Platform",
        tuple(ComponentSpec(k, k.upper(), ComponentType.API, Criticality.LOW) for k in keys),
        tuple(DependencySpec(a, b, FLOW) for a, b in edges),
    )


def test_acyclic_topology_is_accepted() -> None:
    assert len(spec(("b", "a"), ("c", "b"), ("c", "a")).dependencies) == 3


def test_cycle_is_rejected() -> None:
    with pytest.raises(TopologyError, match="cycle"):
        spec(("b", "a"), ("c", "b"), ("a", "c"))


def test_self_dependency_is_rejected() -> None:
    with pytest.raises(TopologyError, match="itself"):
        spec(("a", "a"))


def test_unknown_endpoint_is_rejected() -> None:
    with pytest.raises(TopologyError, match="unknown"):
        TopologySpec(
            "p",
            "Platform",
            (ComponentSpec("a", "A", ComponentType.API, Criticality.LOW),),
            (DependencySpec("a", "ghost", FLOW),),
        )


def test_duplicate_component_key_is_rejected() -> None:
    component = ComponentSpec("a", "A", ComponentType.API, Criticality.LOW)
    with pytest.raises(TopologyError, match="unique"):
        TopologySpec("p", "Platform", (component, component), ())


@pytest.mark.parametrize("key", ["", "A", "-a", "a-", "a_b", "a" * 65])
def test_invalid_component_key_is_rejected(key: str) -> None:
    with pytest.raises(TopologyError):
        ComponentSpec(key, "Name", ComponentType.API, Criticality.LOW)


def test_downstream_is_transitive() -> None:
    topology = spec(("b", "a"), ("c", "b"), ("d", "a"))

    assert downstream_of("a", topology.dependencies) == {"b", "c", "d"}
    assert downstream_of("c", topology.dependencies) == frozenset()


def test_simulated_platform_matches_architecture_topology() -> None:
    topology = SIMULATED_PLATFORM.topology()
    components = {c.key: (c.type, c.criticality) for c in topology.components}
    edges = {(d.dependent, d.dependency) for d in topology.dependencies}

    assert components == {
        "plc-sim-01": (ComponentType.SOURCE, Criticality.HIGH),
        "edge-gateway-01": (ComponentType.GATEWAY, Criticality.HIGH),
        "collector-01": (ComponentType.COLLECTOR, Criticality.HIGH),
        "historian-01": (ComponentType.HISTORIAN, Criticality.HIGH),
        "timeseries-db-01": (ComponentType.DATABASE, Criticality.HIGH),
        "data-api-01": (ComponentType.API, Criticality.MEDIUM),
        "analytics-01": (ComponentType.ANALYTICS, Criticality.LOW),
    }
    assert edges == {
        ("edge-gateway-01", "plc-sim-01"),
        ("collector-01", "edge-gateway-01"),
        ("historian-01", "collector-01"),
        ("historian-01", "timeseries-db-01"),
        ("data-api-01", "historian-01"),
        ("analytics-01", "data-api-01"),
    }
    assert SIMULATED_PLATFORM.downstream("collector-01") == {
        "historian-01",
        "data-api-01",
        "analytics-01",
    }
