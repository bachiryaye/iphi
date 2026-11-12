"""The fictional seven-component platform of architecture §05.6, with nominal operating points."""

from dataclasses import dataclass

from app.topology.domain import (
    ComponentSpec,
    ComponentType,
    Criticality,
    DependencyKind,
    DependencySpec,
    TopologySpec,
    downstream_of,
)


@dataclass(frozen=True, slots=True)
class NominalProfile:
    """Healthy operating point; `None` means the component does not expose that metric.

    Values sit well inside the clear thresholds of the default rules (architecture §05.3), so
    the baseline stays Healthy whatever the seed.
    """

    latency_ms: float
    cpu_pct: float
    mem_pct: float
    queue_depth: float | None = None
    data_age_s: float | None = None


@dataclass(frozen=True, slots=True)
class SimulatedComponent:
    spec: ComponentSpec
    profile: NominalProfile

    @property
    def key(self) -> str:
        return self.spec.key


@dataclass(frozen=True, slots=True)
class SimulatedPlatform:
    key: str
    name: str
    components: tuple[SimulatedComponent, ...]
    dependencies: tuple[DependencySpec, ...]

    def __post_init__(self) -> None:
        self.topology()

    def topology(self) -> TopologySpec:
        """Validated topology (unique keys, known endpoints, acyclic)."""
        return TopologySpec(
            platform_key=self.key,
            platform_name=self.name,
            components=tuple(c.spec for c in self.components),
            dependencies=self.dependencies,
        )

    def component(self, key: str) -> SimulatedComponent | None:
        return next((c for c in self.components if c.key == key), None)

    def downstream(self, key: str) -> frozenset[str]:
        return downstream_of(key, self.dependencies)


def _component(
    key: str, name: str, kind: ComponentType, criticality: Criticality, profile: NominalProfile
) -> SimulatedComponent:
    return SimulatedComponent(ComponentSpec(key, name, kind, criticality), profile)


_HIGH, _MEDIUM, _LOW = Criticality.HIGH, Criticality.MEDIUM, Criticality.LOW
_FLOW, _RUNTIME = DependencyKind.DATA_FLOW, DependencyKind.RUNTIME

SIMULATED_PLATFORM = SimulatedPlatform(
    key="sim-plant-01",
    name="Simulated industrial data platform",
    components=(
        _component(
            "plc-sim-01",
            "PLC simulator 01",
            ComponentType.SOURCE,
            _HIGH,
            NominalProfile(latency_ms=8, cpu_pct=12, mem_pct=30),
        ),
        _component(
            "edge-gateway-01",
            "Edge gateway 01",
            ComponentType.GATEWAY,
            _HIGH,
            NominalProfile(latency_ms=45, cpu_pct=25, mem_pct=40, queue_depth=40),
        ),
        _component(
            "collector-01",
            "Collector 01",
            ComponentType.COLLECTOR,
            _HIGH,
            NominalProfile(latency_ms=35, cpu_pct=30, mem_pct=45, queue_depth=60),
        ),
        _component(
            "historian-01",
            "Historian 01",
            ComponentType.HISTORIAN,
            _HIGH,
            NominalProfile(latency_ms=60, cpu_pct=35, mem_pct=55, data_age_s=4),
        ),
        _component(
            "timeseries-db-01",
            "Time-series database 01",
            ComponentType.DATABASE,
            _HIGH,
            NominalProfile(latency_ms=12, cpu_pct=40, mem_pct=60),
        ),
        _component(
            "data-api-01",
            "Data API 01",
            ComponentType.API,
            _MEDIUM,
            NominalProfile(latency_ms=85, cpu_pct=20, mem_pct=35),
        ),
        _component(
            "analytics-01",
            "Analytics 01",
            ComponentType.ANALYTICS,
            _LOW,
            NominalProfile(latency_ms=120, cpu_pct=45, mem_pct=50, data_age_s=15),
        ),
    ),
    dependencies=(
        DependencySpec("edge-gateway-01", "plc-sim-01", _FLOW),
        DependencySpec("collector-01", "edge-gateway-01", _FLOW),
        DependencySpec("historian-01", "collector-01", _FLOW),
        DependencySpec("historian-01", "timeseries-db-01", _RUNTIME),
        DependencySpec("data-api-01", "historian-01", _FLOW),
        DependencySpec("analytics-01", "data-api-01", _FLOW),
    ),
)
