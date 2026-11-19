import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import paho.mqtt.client as mqtt
import structlog
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from app.connectors.domain import CollectionRequest, CollectionResult, ConnectorIssue
from app.connectors.mqtt.schema import (
    MAX_PACKETS,
    MAX_PAYLOAD_BYTES,
    PACKET_ADAPTER,
    CollectRequest,
    Completion,
    LogsPacket,
    MetricsPacket,
    Packet,
    encode,
    issues,
    observations,
    require_labels,
)
from app.core.observation import ObservationSource, tick_of, tick_time
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.simulation.domain.runs import ScenarioRun

MQTT_CONNECTOR_KEY = "mqtt"
log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MqttConfig:
    host: str
    port: int
    timeout_s: float


def topic(suffix: str) -> str:
    return f"iphi/{SIMULATED_PLATFORM.key}/{suffix}"


def packet_topic(packet: Packet) -> str:
    if isinstance(packet, Completion):
        return topic(f"batches/{packet.request_id}")
    return topic(f"{packet.component}/{packet.kind}")


class Batch:
    """A complete correlated batch only; QoS 1 redelivery never adds observations twice."""

    def __init__(self, request: CollectRequest) -> None:
        self.request = request
        self._packets: dict[int, MetricsPacket | LogsPacket] = {}
        self._completion: Completion | None = None

    def accept(self, received_topic: str, payload: bytes, retained: bool) -> None:
        if retained or len(payload) > MAX_PAYLOAD_BYTES:
            raise ValueError("Retained or oversized MQTT message")
        packet = PACKET_ADAPTER.validate_json(payload)
        require_labels(packet)
        if packet.request_id != self.request.request_id:
            return
        if packet.baseline_id != self.request.baseline_id or received_topic != packet_topic(packet):
            raise ValueError("MQTT topic or baseline mismatch")
        if isinstance(packet, Completion):
            if packet.watermark != tick_time(tick_of(self.request.now)):
                raise ValueError("MQTT completion watermark mismatch")
            if self._completion is not None and self._completion != packet:
                raise ValueError("Conflicting MQTT completion")
            self._completion = packet
        else:
            self._accept_data(packet)

    def _accept_data(self, packet: MetricsPacket | LogsPacket) -> None:
        if SIMULATED_PLATFORM.component(packet.component) is None:
            raise ValueError("Unknown MQTT component")
        if any(row.observed_at > self.request.now for row in packet.rows):
            raise ValueError("MQTT observation exceeds collection time")
        prior = self._packets.get(packet.sequence)
        if prior is not None and prior != packet:
            raise ValueError("Conflicting MQTT redelivery")
        self._packets[packet.sequence] = packet

    def result(self) -> CollectionResult | None:
        completion = self._completion
        if completion is None:
            return None
        if any(index >= completion.packets for index in self._packets):
            raise ValueError("MQTT packet exceeds completion count")
        if len(self._packets) != completion.packets:
            return None
        parts = [observations(self._packets[i]) for i in range(completion.packets)]
        samples = tuple(s for part in parts for s in part.samples)
        logs = tuple(s for part in parts for s in part.logs)
        if len(samples) != completion.samples or len(logs) != completion.logs:
            raise ValueError("MQTT observation count mismatch")
        return CollectionResult(samples, logs, issues(completion), completion.watermark)


class MqttConnector:
    key = MQTT_CONNECTOR_KEY
    source = ObservationSource.MQTT

    def __init__(self, config: MqttConfig, baseline: Callable[[], ScenarioRun]) -> None:
        self._config = config
        self._baseline = baseline

    def collect(self, request: CollectionRequest) -> CollectionResult:
        baseline = self._baseline()
        wire_request = CollectRequest(
            request_id=uuid.uuid4(),
            baseline_id=baseline.id,
            now=request.now,
            resume_after=request.resume_after,
            not_before=request.not_before,
        )
        exchange = _Exchange(self._config, wire_request)
        try:
            return exchange.collect()
        except OSError, TimeoutError, ValueError:
            log.warning(
                "mqtt.collection_failed",
                request_id=str(wire_request.request_id),
                error_code=exchange.error_code,
                environment="simulation",
            )
            # Advance even on loss: a frozen cursor would prevent telemetry-loss evaluation.
            return CollectionResult(
                issues=(
                    ConnectorIssue(
                        exchange.error_code, "MQTT batch unavailable; no partial data accepted."
                    ),
                ),
                watermark=tick_time(tick_of(request.now)),
            )
        finally:
            exchange.close()


class _Exchange:
    def __init__(self, config: MqttConfig, request: CollectRequest) -> None:
        self.config, self.request = config, request
        self.batch = Batch(request)
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2, reconnect_on_failure=False)
        self.client.connect_timeout = min(1.0, config.timeout_s)
        self.client.max_queued_messages_set(MAX_PACKETS)
        self.client.on_message = self._message
        self.client.on_subscribe = self._subscribed
        self.subscribed = False
        self.invalid = False
        self.messages = 0
        self.error_code = "MQTT_UNAVAILABLE"

    def collect(self) -> CollectionResult:
        deadline = time.monotonic() + self.config.timeout_s
        self.client.connect(self.config.host, self.config.port, keepalive=30)
        self._pump_until(self.client.is_connected, deadline)
        rc, _ = self.client.subscribe(
            [
                (topic("+/metrics"), 1),
                (topic("+/logs"), 1),
                (topic(f"batches/{self.request.request_id}"), 1),
            ]
        )
        if rc != mqtt.MQTT_ERR_SUCCESS:
            raise OSError("MQTT subscription failed")
        self._pump_until(lambda: self.subscribed, deadline)
        published = self.client.publish(topic("simulation/collect"), encode(self.request), qos=1)
        if published.rc != mqtt.MQTT_ERR_SUCCESS:
            raise OSError("MQTT request failed")
        self.error_code = "MQTT_BATCH_TIMEOUT"
        while time.monotonic() < deadline:
            self._pump(deadline)
            if self.invalid:
                self.error_code = "MQTT_INVALID_BATCH"
                raise ValueError("Invalid MQTT batch")
            try:
                result = self.batch.result()
            except ValueError:
                self.error_code = "MQTT_INVALID_BATCH"
                raise
            if result is not None:
                return result
        raise TimeoutError("MQTT batch timed out")

    def _pump_until(self, ready: Callable[[], bool], deadline: float) -> None:
        while not ready():
            if time.monotonic() >= deadline:
                raise TimeoutError("MQTT handshake timed out")
            self._pump(deadline)

    def _pump(self, deadline: float) -> None:
        rc = self.client.loop(timeout=max(0.001, min(0.05, deadline - time.monotonic())))
        if rc != mqtt.MQTT_ERR_SUCCESS:
            raise OSError("MQTT connection lost")

    def _subscribed(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _mid: int,
        reason_codes: list[ReasonCode],
        _properties: Properties | None,
    ) -> None:
        self.subscribed = bool(reason_codes) and all(not c.is_failure for c in reason_codes)

    def _message(self, _client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        self.messages += 1
        if self.messages > MAX_PACKETS * 2 + 1:
            self.invalid = True
            return
        try:
            self.batch.accept(message.topic, bytes(message.payload), message.retain)
        except ValueError:
            self.invalid = True

    def close(self) -> None:
        self.client.disconnect()
