"""Enabled connectors, registered explicitly (rules.md P-02); US-12 adds MQTT here."""

from app.connectors.domain import Connector
from app.connectors.simulation import SIMULATION_CONNECTOR_KEY, SimulatedSource, SimulationConnector

ENABLED_CONNECTOR_KEYS: tuple[str, ...] = (SIMULATION_CONNECTOR_KEY,)


def build_connectors(simulation: SimulatedSource) -> list[Connector]:
    return [SimulationConnector(simulation)]
