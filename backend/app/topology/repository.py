import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    delete,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base, check_in
from app.topology.domain import (
    SIMULATION_ENVIRONMENT,
    Component,
    ComponentSpec,
    ComponentType,
    Criticality,
    Dependency,
    DependencyKind,
    DependencySpec,
)


class PlatformRecord(Base):
    __tablename__ = "platform"
    # V1 only hosts simulated platforms; lifting this requires an ADR (architecture §03.1).
    __table_args__ = (CheckConstraint("environment = 'simulation'", name="environment_v1"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    environment: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ComponentRecord(Base):
    __tablename__ = "component"
    __table_args__ = (
        UniqueConstraint("platform_id", "key"),
        CheckConstraint(check_in("type", ComponentType), name="type"),
        CheckConstraint(check_in("criticality", Criticality), name="criticality"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    platform_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.id"))
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    type: Mapped[str] = mapped_column(String(16))
    criticality: Mapped[str] = mapped_column(String(8))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DependencyRecord(Base):
    """`dependent` depends on `dependency` (architecture §03.1); acyclicity is checked at seed."""

    __tablename__ = "dependency"
    __table_args__ = (
        UniqueConstraint("dependent_component_id", "dependency_component_id"),
        CheckConstraint("dependent_component_id <> dependency_component_id", name="not_self"),
        CheckConstraint(check_in("kind", DependencyKind), name="kind"),
        Index("ix_dependency_dependency_component_id", "dependency_component_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    platform_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.id"))
    dependent_component_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("component.id"))
    dependency_component_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("component.id"))
    kind: Mapped[str] = mapped_column(String(16))


def _to_component(record: ComponentRecord) -> Component:
    return Component(
        id=record.id,
        key=record.key,
        name=record.name,
        type=ComponentType(record.type),
        criticality=Criticality(record.criticality),
    )


class TopologyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_platform(self, key: str, name: str) -> uuid.UUID:
        statement = (
            insert(PlatformRecord)
            .values(id=uuid.uuid7(), key=key, name=name, environment=SIMULATION_ENVIRONMENT)
            .on_conflict_do_update(index_elements=["key"], set_={"name": name})
            .returning(PlatformRecord.id)
        )
        return self._session.execute(statement).scalar_one()

    def platforms(self) -> list[PlatformRecord]:
        return list(self._session.scalars(select(PlatformRecord).order_by(PlatformRecord.key)))

    def upsert_component(self, platform_id: uuid.UUID, spec: ComponentSpec) -> None:
        changes = {
            "name": spec.name,
            "type": spec.type.value,
            "criticality": spec.criticality.value,
        }
        statement = (
            insert(ComponentRecord)
            .values(id=uuid.uuid7(), platform_id=platform_id, key=spec.key, **changes)
            .on_conflict_do_update(index_elements=["platform_id", "key"], set_=changes)
        )
        self._session.execute(statement)

    def components(self, platform_id: uuid.UUID) -> list[Component]:
        records = self._session.scalars(
            select(ComponentRecord)
            .where(ComponentRecord.platform_id == platform_id)
            .order_by(ComponentRecord.key)
        )
        return [_to_component(r) for r in records]

    def dependencies(self, platform_id: uuid.UUID) -> list[Dependency]:
        records = self._session.scalars(
            select(DependencyRecord)
            .where(DependencyRecord.platform_id == platform_id)
            .order_by(
                DependencyRecord.dependent_component_id, DependencyRecord.dependency_component_id
            )
        )
        return [
            Dependency(r.dependent_component_id, r.dependency_component_id, DependencyKind(r.kind))
            for r in records
        ]

    def replace_dependencies(
        self,
        platform_id: uuid.UUID,
        ids_by_key: dict[str, uuid.UUID],
        dependencies: Sequence[DependencySpec],
    ) -> None:
        # Edges carry no history and are never evidence, so the seed rewrites them wholesale.
        self._session.execute(
            delete(DependencyRecord).where(DependencyRecord.platform_id == platform_id)
        )
        self._session.add_all(
            DependencyRecord(
                platform_id=platform_id,
                dependent_component_id=ids_by_key[d.dependent],
                dependency_component_id=ids_by_key[d.dependency],
                kind=d.kind.value,
            )
            for d in dependencies
        )
