"""Direct observation writes for tests that need a history validation would refuse (too old)."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from app.core.observation import LogSeverity, ObservationSource, Quality
from app.ingestion.domain.validation import AcceptedLog, AcceptedSample, log_fingerprint
from app.ingestion.repository import CollectionRunRepository, ObservationRepository
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.topology.service import TopologyService


def component_id(session_factory: sessionmaker[Session], key: str) -> uuid.UUID:
    topology = TopologyService(session_factory).platform(SIMULATED_PLATFORM.key)
    assert topology is not None
    component = topology.component(key)
    assert component is not None
    return component.id


def insert_samples(
    session_factory: sessionmaker[Session],
    component: uuid.UUID,
    points: Sequence[tuple[datetime, float]],
    metric: tuple[str, str] = ("up", "bool"),
) -> None:
    name, unit = metric
    received = max(at for at, _ in points)
    with session_factory.begin() as session:
        run_id = CollectionRunRepository(session).open(
            "test", ObservationSource.SIMULATION, received
        )
        ObservationRepository(session).insert_samples(
            [AcceptedSample(component, name, v, unit, Quality.GOOD, at, None) for at, v in points],
            ObservationSource.SIMULATION,
            run_id,
            received,
        )


def insert_logs(
    session_factory: sessionmaker[Session],
    component: uuid.UUID,
    logs: Sequence[tuple[datetime, LogSeverity, str]],
) -> None:
    received = max(at for at, _, _ in logs)
    with session_factory.begin() as session:
        run_id = CollectionRunRepository(session).open(
            "test", ObservationSource.SIMULATION, received
        )
        ObservationRepository(session).insert_logs(
            [
                AcceptedLog(
                    component,
                    severity,
                    message,
                    log_fingerprint(severity, message),
                    uuid.uuid4().hex,
                    {},
                    at,
                    None,
                )
                for at, severity, message in logs
            ],
            ObservationSource.SIMULATION,
            run_id,
            received,
        )
