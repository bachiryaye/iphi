import uuid
from http import HTTPStatus

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import IphiError
from app.health.domain.history import CONTINUITY, HistoryPoint, HistoryTail
from app.health.domain.states import HealthState
from app.health.repository import HealthRuleRecord, RuleEvaluationRecord, RuleStateRecord
from app.ingestion.domain.series import TimeWindow

MAX_HISTORY_ROWS = 100_000


class HistoryTooDenseError(IphiError):
    code = "HISTORY_TOO_DENSE"
    status = HTTPStatus.REQUEST_ENTITY_TOO_LARGE


class HistoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def points(self, component_id: uuid.UUID, window: TimeWindow) -> list[HistoryPoint]:
        e, r = RuleEvaluationRecord, HealthRuleRecord
        rows = self._session.execute(
            select(r.key, r.version, e.evaluated_at, e.state, e.id)
            .join(r, r.id == e.rule_id)
            .where(
                e.component_id == component_id,
                e.evaluated_at >= window.start - CONTINUITY,
                e.evaluated_at < window.end + CONTINUITY,
            )
            .order_by(e.evaluated_at, e.id)
            .limit(MAX_HISTORY_ROWS + 1)
        ).all()
        if len(rows) > MAX_HISTORY_ROWS:
            raise HistoryTooDenseError("Choose a smaller state-history window.")
        return [
            HistoryPoint(key, version, at, HealthState(state), identifier)
            for key, version, at, state, identifier in rows
        ]

    def tails(self, component_id: uuid.UUID) -> list[HistoryTail]:
        r = RuleStateRecord
        rows = self._session.execute(
            select(r.rule_key, r.last_evaluated_at, r.since, r.state).where(
                r.component_id == component_id
            )
        ).all()
        return [HistoryTail(key, at, since, HealthState(state)) for key, at, since, state in rows]
