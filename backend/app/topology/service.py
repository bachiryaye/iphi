import structlog
from sqlalchemy.orm import Session, sessionmaker

from app.topology.domain import PlatformTopology, TopologySpec
from app.topology.repository import TopologyRepository

log = structlog.get_logger(__name__)


class TopologyService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def ensure(self, spec: TopologySpec) -> None:
        """Idempotent seed: upserts the platform and components, rewrites the dependency edges."""
        with self._session_factory.begin() as session:
            repository = TopologyRepository(session)
            platform_id = repository.upsert_platform(spec.platform_key, spec.platform_name)
            for component in spec.components:
                repository.upsert_component(platform_id, component)
            ids_by_key = {c.key: c.id for c in repository.components(platform_id)}
            repository.replace_dependencies(platform_id, ids_by_key, spec.dependencies)
        declared = {c.key for c in spec.components}
        undeclared = sorted(ids_by_key.keys() - declared)
        if undeclared:
            # Components may already be referenced by observations, so they are kept, not deleted.
            log.warning(
                "topology.undeclared_components", platform=spec.platform_key, keys=undeclared
            )
        log.info(
            "topology.seeded",
            platform=spec.platform_key,
            components=len(spec.components),
            dependencies=len(spec.dependencies),
        )

    def platform(self, platform_key: str) -> PlatformTopology | None:
        with self._session_factory() as session:
            repository = TopologyRepository(session)
            platform_id = repository.platform_id(platform_key)
            if platform_id is None:
                return None
            components = tuple(repository.components(platform_id))
        return PlatformTopology(platform_id, components)
