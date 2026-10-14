"""
Unit tests for MQTT Gateway Adapter.
"""

from datetime import datetime, timezone
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from storage.database import Base
from storage.repositories import RawDataRepository
from ingestion.ingestion_service import IngestionService
from ingestion.mqtt_adapter import MQTTGatewayAdapter, simulate_mqtt_publish


@pytest.fixture
def mqtt_setup():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()

    raw_repo = RawDataRepository(session)
    ingestion_service = IngestionService(raw_repo)
    adapter = MQTTGatewayAdapter(ingestion_service)

    yield adapter, raw_repo, session
    session.close()


def test_mqtt_topic_parsing(mqtt_setup):
    adapter, _, _ = mqtt_setup
    topic = "factory/Zone-East/M05/S042/telemetry"
    parsed = adapter.parse_topic(topic)

    assert parsed["factory_zone"] == "Zone-East"
    assert parsed["machine_id"] == "M05"
    assert parsed["sensor_id"] == "S042"


def test_mqtt_message_ingestion(mqtt_setup):
    adapter, raw_repo, session = mqtt_setup
    result = simulate_mqtt_publish(
        adapter,
        sensor_id="S042",
        machine_id="M05",
        zone="Zone-East",
        temp=52.3,
        press=4.1,
        vib=1.2,
    )
    session.commit()

    assert result.received == 1
    assert result.accepted == 1
    assert raw_repo.count() == 1
