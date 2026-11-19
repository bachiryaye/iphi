"""One transport per simulated platform; never mix duplicate sources (ADR 0026)."""

from app.connectors.domain import Connector
from app.connectors.mqtt.adapter import MqttConfig, MqttConnector
from app.connectors.simulation import SimulationConnector
from app.core.observation import ObservationSource
from app.core.settings import Settings
from app.simulation.service import SimulationService


def enabled_connector_keys(source: ObservationSource) -> tuple[str, ...]:
    return (source.value,)


def build_connectors(
    simulation: SimulationService, settings: Settings | None = None
) -> list[Connector]:
    if settings is not None and settings.connector_source is ObservationSource.MQTT:
        config = MqttConfig(settings.mqtt_host, settings.mqtt_port, settings.mqtt_timeout_s)
        return [MqttConnector(config, simulation.baseline)]
    return [SimulationConnector(simulation)]
