import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.observation import SAMPLE_INTERVAL
from app.health.domain.freshness import ReadContext
from app.health.domain.history import HistoryData, HistoryPolicy, StateHistory, state_history
from app.health.history_repository import HistoryRepository
from app.health.service import ComponentRef, HealthReader, HistoryOrigin
from app.ingestion.domain.series import TimeWindow
from app.topology.domain import ComponentNotFoundError
from app.topology.service import TopologyService


@dataclass(frozen=True, slots=True)
class StateHistoryView:
    component: ComponentRef
    window: TimeWindow
    reset_at: datetime | None
    history: StateHistory


class StateHistoryQueries:
    def __init__(
        self, factory: sessionmaker[Session], topology: TopologyService, origin: HistoryOrigin
    ) -> None:
        self._factory, self._topology, self._origin = factory, topology, origin

    def component(
        self, component_id: uuid.UUID, window: TimeWindow, context: ReadContext, max_segments: int
    ) -> StateHistoryView:
        window = TimeWindow(window.start.astimezone(UTC), window.end.astimezone(UTC))
        component = next(
            (c for p in self._topology.platforms() for c in p.components if c.id == component_id),
            None,
        )
        if component is None:
            raise ComponentNotFoundError(f"No component {component_id}.")
        with self._factory.begin() as session:
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            repository = HistoryRepository(session)
            rules = [
                (r.key, r.version)
                for r in HealthReader(session).active_rules()
                if r.applies_to(component)
            ]
            data = HistoryData(
                repository.points(component_id, window),
                repository.tails(component_id),
                rules,
                self._origin.history_start(session),
            )
        result = state_history(
            data, HistoryPolicy(window, max_segments, context.max_age or SAMPLE_INTERVAL)
        )
        return StateHistoryView(
            ComponentRef(component.id, component.key), window, data.reset_at, result
        )
