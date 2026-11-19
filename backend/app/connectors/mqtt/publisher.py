import signal
import threading
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from queue import Empty, Full, Queue
from types import FrameType

import paho.mqtt.client as mqtt
import structlog
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from app.connectors.domain import CollectionRequest
from app.connectors.mqtt.adapter import MqttConfig, packet_topic, topic
from app.connectors.mqtt.schema import (
    MAX_PAYLOAD_BYTES,
    MAX_REQUEST_QUEUE,
    CollectRequest,
    encode,
    packets,
    require_labels,
)
from app.connectors.simulation import SimulationConnector
from app.core.clock import WallClock
from app.core.db import create_db_engine, create_session_factory
from app.core.liveness import LivenessFile
from app.core.logging import configure_logging
from app.core.settings import Settings
from app.simulation.service import SimulationService, build_simulation

log = structlog.get_logger(__name__)


class SimulatedPublisher:
    """Read-only simulation publisher; the worker owns time, ingestion and domain decisions."""

    def __init__(self, simulation: SimulationService, config: MqttConfig) -> None:
        self.simulation, self.config = simulation, config
        self.ready = threading.Event()
        self._requests: Queue[tuple[CollectRequest, float]] = Queue(MAX_REQUEST_QUEUE)
        self._client = mqtt.Client(CallbackAPIVersion.VERSION2)
        self._client.connect_timeout = min(1.0, config.timeout_s)
        self._client.max_queued_messages_set(16)
        self._client.reconnect_delay_set(min_delay=1, max_delay=10)
        self._client.on_connect = self._connected
        self._client.on_disconnect = self._disconnected
        self._client.on_subscribe = self._subscribed
        self._client.on_message = self._message

    def run(self, stop: threading.Event, alive: Callable[[], None] = lambda: None) -> None:
        self._client.connect_async(self.config.host, self.config.port, keepalive=30)
        self._client.loop_start()
        try:
            while not stop.is_set():
                if self.ready.is_set():
                    alive()
                try:
                    request, received = self._requests.get(timeout=0.2)
                except Empty:
                    continue
                if time.monotonic() - received > self.config.timeout_s:
                    continue
                try:
                    self._publish(request, received + self.config.timeout_s, stop)
                except Exception as exc:  # noqa: BLE001 - process boundary, sanitized log
                    # DB/network exception text can contain private configuration.
                    log.error(
                        "mqtt.publisher_failed",
                        error_type=type(exc).__name__,
                        request_id=str(request.request_id),
                        environment="simulation",
                    )
        finally:
            self._client.disconnect()
            self._client.loop_stop()
            self.ready.clear()

    def _publish(self, request: CollectRequest, deadline: float, stop: threading.Event) -> None:
        if request.baseline_id != self.simulation.baseline().id:
            raise ValueError("Obsolete simulation baseline")
        if request.now > self.simulation.clock().platform_time + timedelta(seconds=30):
            raise ValueError("Collection time exceeds platform time")
        if request.not_before != request.now - timedelta(minutes=10):
            raise ValueError("Collection lookback must be ten platform minutes")
        if request.resume_after is not None and request.resume_after > request.now:
            raise ValueError("Collection cursor exceeds platform time")
        result = SimulationConnector(self.simulation).collect(
            CollectionRequest(
                request.now,
                request.resume_after,
                request.not_before,
            )
        )
        for packet in packets(result, request):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or stop.is_set():
                raise TimeoutError("Simulation publication deadline reached")
            sent = self._client.publish(packet_topic(packet), encode(packet), qos=1, retain=False)
            sent.wait_for_publish(timeout=remaining)
            if not sent.is_published():
                raise TimeoutError("Simulation publication not acknowledged")

    def _connected(
        self,
        client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.ConnectFlags,
        reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        if not reason_code.is_failure:
            client.subscribe(topic("simulation/collect"), qos=1)

    def _subscribed(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _mid: int,
        reason_codes: list[ReasonCode],
        _properties: Properties | None,
    ) -> None:
        if reason_codes and all(not r.is_failure for r in reason_codes):
            self.ready.set()
            log.info("mqtt.publisher_ready", environment="simulation")

    def _disconnected(
        self,
        _client: mqtt.Client,
        _userdata: object,
        _flags: mqtt.DisconnectFlags,
        _reason_code: ReasonCode,
        _properties: Properties | None,
    ) -> None:
        self.ready.clear()

    def _message(self, _client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        if message.retain or len(message.payload) > MAX_PAYLOAD_BYTES:
            log.warning("mqtt.request_rejected", error_code="MQTT_INVALID_REQUEST")
            return
        try:
            request = CollectRequest.model_validate_json(message.payload)
            require_labels(request)
            self._requests.put_nowait((request, time.monotonic()))
        except ValueError, Full:
            log.warning("mqtt.request_rejected", error_code="MQTT_INVALID_REQUEST")


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level, settings.log_format)
    stop = threading.Event()

    def request_stop(_signum: int, _frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    engine = create_db_engine(settings)
    simulation = build_simulation(create_session_factory(engine), WallClock())
    publisher = SimulatedPublisher(
        simulation,
        MqttConfig(
            settings.mqtt_host,
            settings.mqtt_port,
            settings.mqtt_timeout_s,
        ),
    )
    try:
        publisher.run(stop, LivenessFile(Path(settings.liveness_file)).touch)
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
