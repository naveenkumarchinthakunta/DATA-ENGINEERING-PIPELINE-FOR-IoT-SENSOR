"""
Unit and Integration tests for Storage Layer and Repositories.
Uses an isolated in-memory SQLite database to ensure clean, repeatable testing.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from storage.database import Base
from storage.repositories import (
    SensorRepository,
    RawDataRepository,
    ProcessedDataRepository,
    RejectedDataRepository,
    AlertRepository,
    PipelineRunRepository,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


def test_sensor_repository_upsert(db_session):
    repo = SensorRepository(db_session)
    data = [
        {
            "sensor_id": "S001",
            "machine_id": "M01",
            "factory_zone": "Zone-A",
            "sensor_status": "ACTIVE",
        },
        {
            "sensor_id": "S002",
            "machine_id": "M01",
            "factory_zone": "Zone-A",
            "sensor_status": "INACTIVE",
        },
    ]
    count = repo.upsert_sensors(data)
    db_session.commit()
    assert count == 2
    assert repo.count() == 2

    # Query filtered
    active = repo.get_all(status="ACTIVE")
    assert len(active) == 1
    assert active[0].sensor_id == "S001"


def test_raw_repository_deduplication(db_session):
    repo = RawDataRepository(db_session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    records = [
        {
            "event_id": "evt_r1",
            "sensor_id": "S001",
            "event_timestamp": now,
            "raw_payload": {"test": 1},
        },
        {
            "event_id": "evt_r2",
            "sensor_id": "S002",
            "event_timestamp": now,
            "raw_payload": {"test": 2},
        },
    ]
    inserted, dups = repo.save_batch(records)
    db_session.commit()
    assert inserted == 2
    assert dups == 0

    # Retry inserting same records
    ins2, dups2 = repo.save_batch(records)
    db_session.commit()
    assert ins2 == 0
    assert dups2 == 2
    assert repo.count() == 2


def test_processed_repository_persistence(db_session):
    repo = ProcessedDataRepository(db_session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    records = [
        {
            "event_id": "evt_p1",
            "sensor_id": "S001",
            "machine_id": "M01",
            "event_timestamp": now,
            "temperature_celsius": 45.0,
            "pressure_bar": 4.0,
            "vibration_mm_s": 1.2,
        }
    ]
    inserted = repo.save_batch(records)
    db_session.commit()
    assert inserted == 1

    readings, total = repo.get_readings_by_sensor("S001")
    assert total == 1
    assert readings[0].event_id == "evt_p1"


def test_rejected_repository_summary(db_session):
    repo = RejectedDataRepository(db_session)
    records = [
        {
            "event_id": "evt_bad1",
            "sensor_id": "S001",
            "raw_payload": {},
            "rejection_reason": "MALFORMED_TIMESTAMP",
        },
        {
            "event_id": "evt_bad2",
            "sensor_id": "S002",
            "raw_payload": {},
            "rejection_reason": "MALFORMED_TIMESTAMP",
        },
        {
            "event_id": "evt_bad3",
            "sensor_id": "S003",
            "raw_payload": {},
            "rejection_reason": "NEGATIVE_ABSOLUTE_PRESSURE",
        },
    ]
    repo.save_batch(records)
    db_session.commit()
    assert repo.count() == 3

    summary = repo.get_rejection_summary()
    assert len(summary) == 2
    assert summary[0]["reason"] == "MALFORMED_TIMESTAMP"
    assert summary[0]["count"] == 2


def test_alert_repository_idempotency_and_ack(db_session):
    repo = AlertRepository(db_session)
    alerts = [
        {
            "alert_id": "alt_1",
            "sensor_id": "S001",
            "machine_id": "M01",
            "event_id": "evt_1",
            "alert_type": "TEMP_HIGH",
            "severity": "CRITICAL",
            "measured_value": 95.0,
            "configured_threshold": 85.0,
        }
    ]
    inserted = repo.save_batch(alerts)
    db_session.commit()
    assert inserted == 1

    # Retry inserting same alert for same event and alert_type
    ins2 = repo.save_batch(alerts)
    db_session.commit()
    assert ins2 == 0  # Deduplicated

    # Acknowledge
    success = repo.acknowledge_alert("alt_1")
    db_session.commit()
    assert success is True

    fetched, _ = repo.get_alerts(status="ACKNOWLEDGED")
    assert len(fetched) == 1
    assert fetched[0].alert_id == "alt_1"
