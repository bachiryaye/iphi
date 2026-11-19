import json
import uuid
from datetime import timedelta

import pytest
from pydantic import SecretStr, ValidationError

from app.connectors.domain import CollectionRequest
from app.connectors.mqtt.adapter import Batch, packet_topic, topic
from app.connectors.mqtt.schema import (
    MAX_PAYLOAD_BYTES,
    CollectRequest,
    Completion,
    MetricsPacket,
    encode,
    packets,
)
from app.connectors.registry import enabled_connector_keys
from app.connectors.simulation import SimulationConnector
from app.core.observation import ObservationSource
from app.core.settings import Settings
from tests.simulation_runs import GOLDEN_START
from tests.unit.test_simulation_connector import RecordingSource


def request() -> CollectRequest:
    return CollectRequest(
        request_id=uuid.uuid4(),
        baseline_id=uuid.uuid4(),
        now=GOLDEN_START,
        resume_after=None,
        not_before=GOLDEN_START - timedelta(minutes=10),
    )


def metric_packet(wire: CollectRequest) -> MetricsPacket:
    result = SimulationConnector(RecordingSource()).collect(
        CollectionRequest(
            wire.now,
            wire.resume_after,
            wire.not_before,
        )
    )
    packet = next(packets(result, wire))
    assert isinstance(packet, MetricsPacket)
    return packet


def test_ten_minute_batch_roundtrips_observations_quality_and_attribution() -> None:
    wire = request().model_copy(update={"now": GOLDEN_START + timedelta(minutes=10)})
    result = SimulationConnector(RecordingSource()).collect(
        CollectionRequest(
            wire.now,
            wire.resume_after,
            wire.not_before,
        )
    )
    batch = Batch(wire)
    encoded = list(packets(result, wire))

    # Completion can arrive first; repeated QoS 1 packets are still the same observations.
    for packet in reversed(encoded):
        payload = encode(packet)
        assert len(payload) <= MAX_PAYLOAD_BYTES
        batch.accept(packet_topic(packet), payload, False)
        batch.accept(packet_topic(packet), payload, False)

    actual = batch.result()
    assert actual is not None
    assert set(actual.samples) == set(result.samples)
    assert sorted(actual.logs, key=lambda s: (s.component_key, s.observed_at, s.message)) == sorted(
        result.logs, key=lambda s: (s.component_key, s.observed_at, s.message)
    )
    assert actual.watermark == result.watermark
    assert actual.issues == result.issues


@pytest.mark.parametrize(
    "field_value",
    [
        ("version", 2),
        ("environment", "production"),
        ("source", "simulation"),
        ("extra", "ignored"),
        ("sequence", 256),
        ("component", "bad/+/topic"),
    ],
)
def test_invalid_envelope_is_rejected(field_value: tuple[str, object]) -> None:
    wire = request()
    packet = metric_packet(wire)
    body = packet.model_dump(mode="json")
    body[field_value[0]] = field_value[1]

    with pytest.raises(ValueError, match="validation error"):
        Batch(wire).accept(packet_topic(packet), json.dumps(body).encode(), False)


@pytest.mark.parametrize(
    "field_value",
    [
        ("observed_at", "2026-01-01T00:00:00"),
        ("observed_at", "2026-01-02T00:00:00Z"),
        ("value", "NaN"),
        ("value", True),
        ("quality", "healthy"),
        ("scenario_run_id", None),
    ],
)
def test_invalid_metric_row_is_rejected(field_value: tuple[str, object]) -> None:
    wire = request()
    packet = metric_packet(wire)
    body = packet.model_dump(mode="json")
    body["rows"][0][field_value[0]] = field_value[1]

    with pytest.raises(ValueError, match=r"validation error|exceeds collection time"):
        Batch(wire).accept(packet_topic(packet), json.dumps(body).encode(), False)


@pytest.mark.parametrize("mode", ["retained", "oversized", "wrong-topic", "wrong-baseline"])
def test_unsafe_delivery_is_rejected(mode: str) -> None:
    wire = request()
    packet = metric_packet(wire)
    if mode == "wrong-baseline":
        packet = packet.model_copy(update={"baseline_id": uuid.uuid4()})
    payload = b"x" * (MAX_PAYLOAD_BYTES + 1) if mode == "oversized" else encode(packet)

    with pytest.raises(ValueError, match="MQTT"):
        Batch(wire).accept(
            topic("other/metrics") if mode == "wrong-topic" else packet_topic(packet),
            payload,
            mode == "retained",
        )


def test_unrelated_request_is_ignored_and_partial_batch_is_not_accepted() -> None:
    wire = request()
    packet = metric_packet(wire)
    batch = Batch(wire)
    unrelated = packet.model_copy(update={"request_id": uuid.uuid4()})
    batch.accept(packet_topic(unrelated), encode(unrelated), False)
    assert batch.result() is None
    completion = Completion(
        request_id=wire.request_id,
        baseline_id=wire.baseline_id,
        packets=2,
        samples=2,
        logs=0,
        watermark=wire.now,
    )
    batch.accept(packet_topic(completion), encode(completion), False)
    batch.accept(packet_topic(packet), encode(packet), False)
    assert batch.result() is None


def test_conflicting_redelivery_is_rejected() -> None:
    wire = request()
    packet = metric_packet(wire)
    batch = Batch(wire)
    batch.accept(packet_topic(packet), encode(packet), False)
    changed = packet.model_copy(
        update={
            "rows": [
                packet.rows[0].model_copy(update={"value": 99.0}),
                *packet.rows[1:],
            ]
        }
    )

    with pytest.raises(ValueError, match="Conflicting"):
        batch.accept(packet_topic(changed), encode(changed), False)


def test_false_completion_counts_are_rejected() -> None:
    wire = request()
    packet = metric_packet(wire).model_copy(update={"sequence": 0})
    batch = Batch(wire)
    completion = Completion(
        request_id=wire.request_id,
        baseline_id=wire.baseline_id,
        packets=1,
        samples=0,
        logs=0,
        watermark=wire.now,
    )
    for item in (packet, completion):
        batch.accept(packet_topic(item), encode(item), False)

    with pytest.raises(ValueError, match="count mismatch"):
        batch.result()


@pytest.mark.parametrize("label", ["version", "environment", "source"])
def test_transport_labels_must_be_explicit(label: str) -> None:
    wire = request()
    packet = metric_packet(wire)
    body = packet.model_dump(mode="json")
    del body[label]
    with pytest.raises(ValueError, match="require explicit"):
        Batch(wire).accept(packet_topic(packet), json.dumps(body).encode(), False)


def test_first_collection_between_slots_completes_without_fabricating_observations() -> None:
    wire = request().model_copy(update={"now": GOLDEN_START + timedelta(seconds=2)})
    source = RecordingSource(started_at=GOLDEN_START + timedelta(seconds=1))
    result = SimulationConnector(source).collect(
        CollectionRequest(
            wire.now,
            wire.resume_after,
            wire.not_before,
        )
    )
    batch = Batch(wire)
    for packet in packets(result, wire):
        batch.accept(packet_topic(packet), encode(packet), False)
    completed = batch.result()
    assert completed is not None
    assert completed.samples == ()
    assert completed.watermark == GOLDEN_START


def test_connector_selection_uses_one_transport_and_rejects_external_hosts() -> None:
    assert enabled_connector_keys(ObservationSource.MQTT) == ("mqtt",)
    assert enabled_connector_keys(ObservationSource.SIMULATION) == ("simulation",)
    with pytest.raises(ValidationError):
        Settings(database_url=SecretStr("unused"), mqtt_host="real-plant.example")
