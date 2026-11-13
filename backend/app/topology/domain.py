import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus

from app.core.exceptions import IphiError

# V1 hosts simulated platforms only (architecture §03.1).
SIMULATION_ENVIRONMENT = "simulation"
COMPONENT_KEY = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?")


class ComponentType(StrEnum):
    """ISA-95 level 2/3 roles along the data path (rules.md S-01)."""

    SOURCE = "source"
    GATEWAY = "gateway"
    COLLECTOR = "collector"
    HISTORIAN = "historian"
    DATABASE = "database"
    API = "api"
    ANALYTICS = "analytics"


class Criticality(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DependencyKind(StrEnum):
    DATA_FLOW = "data_flow"
    RUNTIME = "runtime"


class TopologyError(ValueError):
    pass


class ComponentNotFoundError(IphiError):
    status = HTTPStatus.NOT_FOUND
    code = "COMPONENT_NOT_FOUND"


class PlatformNotFoundError(IphiError):
    status = HTTPStatus.NOT_FOUND
    code = "PLATFORM_NOT_FOUND"


@dataclass(frozen=True, slots=True)
class ComponentSpec:
    key: str
    name: str
    type: ComponentType
    criticality: Criticality

    def __post_init__(self) -> None:
        if not COMPONENT_KEY.fullmatch(self.key):
            raise TopologyError(f"invalid component key {self.key!r}")


@dataclass(frozen=True, slots=True)
class DependencySpec:
    """`dependent` depends on `dependency`; data flows from `dependency` to `dependent`."""

    dependent: str
    dependency: str
    kind: DependencyKind


@dataclass(frozen=True, slots=True)
class TopologySpec:
    platform_key: str
    platform_name: str
    components: tuple[ComponentSpec, ...]
    dependencies: tuple[DependencySpec, ...]

    def __post_init__(self) -> None:
        keys = [c.key for c in self.components]
        if len(set(keys)) != len(keys):
            raise TopologyError("component keys must be unique")
        known = set(keys)
        pairs = [(d.dependent, d.dependency) for d in self.dependencies]
        if len(set(pairs)) != len(pairs):
            raise TopologyError("duplicate dependency")
        for dependent, dependency in pairs:
            if dependent not in known or dependency not in known:
                raise TopologyError(f"dependency {dependent} -> {dependency} names an unknown key")
            if dependent == dependency:
                raise TopologyError(f"component {dependent} cannot depend on itself")
        cycle = find_cycle(known, pairs)
        if cycle:
            raise TopologyError(f"dependency cycle through {', '.join(sorted(cycle))}")


@dataclass(frozen=True, slots=True)
class Component:
    id: uuid.UUID
    key: str
    name: str
    type: ComponentType
    criticality: Criticality


def find_cycle(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> set[str]:
    """Nodes left after Kahn's algorithm; empty when the graph is acyclic."""
    remaining = set(nodes)
    edge_list = list(edges)
    while remaining:
        blocked = {a for a, b in edge_list if a in remaining and b in remaining}
        free = remaining - blocked
        if not free:
            return remaining
        remaining -= free
    return set()


def downstream_of(key: str, dependencies: Iterable[DependencySpec]) -> frozenset[str]:
    """Transitive dependents of `key`, whatever the dependency kind."""
    dependents: dict[str, set[str]] = {}
    for d in dependencies:
        dependents.setdefault(d.dependency, set()).add(d.dependent)
    found: set[str] = set()
    frontier = [key]
    while frontier:
        for child in dependents.get(frontier.pop(), ()):
            if child not in found:
                found.add(child)
                frontier.append(child)
    return frozenset(found)


@dataclass(frozen=True, slots=True)
class Dependency:
    """`dependent_id` depends on `dependency_id` (architecture §03.1)."""

    dependent_id: uuid.UUID
    dependency_id: uuid.UUID
    kind: DependencyKind


def upstream_ids(component_id: uuid.UUID, dependencies: Sequence[Dependency]) -> set[uuid.UUID]:
    """Transitive dependencies of a component, whatever the dependency kind."""
    direct: dict[uuid.UUID, list[uuid.UUID]] = {}
    for d in dependencies:
        direct.setdefault(d.dependent_id, []).append(d.dependency_id)
    found: set[uuid.UUID] = set()
    frontier = [component_id]
    while frontier:
        for parent in direct.get(frontier.pop(), ()):
            if parent not in found:
                found.add(parent)
                frontier.append(parent)
    return found


@dataclass(frozen=True, slots=True)
class PlatformTopology:
    platform_id: uuid.UUID
    key: str
    name: str
    environment: str
    components: tuple[Component, ...]
    dependencies: tuple[Dependency, ...]

    def component(self, key: str) -> Component | None:
        return next((c for c in self.components if c.key == key), None)

    def component_by_id(self, component_id: uuid.UUID) -> Component:
        found = next((c for c in self.components if c.id == component_id), None)
        if found is None:
            raise ComponentNotFoundError(f"No component {component_id}.")
        return found

    def keys_by_id(self) -> dict[uuid.UUID, str]:
        return {c.id: c.key for c in self.components}
