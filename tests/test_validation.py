"""
Unit and Data Quality tests for Data Validation Engine.
"""

from datetime import datetime, timezone, timedelta
import pytest
from validation.validator import DataValidator


@pytest.fixture
def validator():
    return DataValidator(max_future_skew_seconds=120)


def test_valid_record(validator):
    rec = {
        "event_id": "evt_test1",
        "sensor_id": "S001",
        "machine_id": "M01",
        "factory_zone": "Zone-North",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_celsius": 45.2,
        "pressure_bar": 4.5,
        "vibration_mm_s": 1.2,
    }
    outcome = validator.validate_record(rec)
    assert outcome.is_valid is True
    assert outcome.rejection_reason is None
    assert "parsed_event_timestamp" in outcome.record


def test_missing_event_id(validator):
    rec = {
        "sensor_id": "S001",
        "machine_id": "M01",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_celsius": 45.0,
    }
    outcome = validator.validate_record(rec)
    assert outcome.is_valid is False
    assert "SCHEMA_VALIDATION_ERROR" in outcome.rejection_reason


def test_missing_sensor_id(validator):
    rec = {
        "event_id": "evt_test2",
        "machine_id": "M01",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_celsius": 45.0,
    }
    outcome = validator.validate_record(rec)
    assert outcome.is_valid is False
    assert "SCHEMA_VALIDATION_ERROR" in outcome.rejection_reason


def test_malformed_timestamp(validator):
    rec = {
        "event_id": "evt_test3",
        "sensor_id": "S001",
        "machine_id": "M01",
        "event_timestamp": "NOT_A_TIMESTAMP",
        "temperature_celsius": 45.0,
    }
    outcome = validator.validate_record(rec)
    assert outcome.is_valid is False
    assert "MALFORMED_TIMESTAMP" in outcome.rejection_reason


def test_future_timestamp_skew(validator):
    future_time = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    rec = {
        "event_id": "evt_test4",
        "sensor_id": "S001",
        "machine_id": "M01",
        "event_timestamp": future_time,
        "temperature_celsius": 45.0,
    }
    outcome = validator.validate_record(rec)
    assert outcome.is_valid is False
    assert "FUTURE_TIMESTAMP_EXCEEDED_SKEW" in outcome.rejection_reason


def test_nan_measurement_rejection(validator):
    rec = {
        "event_id": "evt_test5",
        "sensor_id": "S001",
        "machine_id": "M01",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_celsius": float("nan"),
    }
    outcome = validator.validate_record(rec)
    assert outcome.is_valid is False
    assert "SCHEMA_VALIDATION_ERROR" in outcome.rejection_reason


def test_negative_absolute_pressure(validator):
    rec = {
        "event_id": "evt_test6",
        "sensor_id": "S001",
        "machine_id": "M01",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "pressure_bar": -2.5,
    }
    outcome = validator.validate_record(rec)
    assert outcome.is_valid is False
    assert "NEGATIVE_ABSOLUTE_PRESSURE" in outcome.rejection_reason


def test_batch_validation_and_intra_batch_duplicates(validator):
    now_iso = datetime.now(timezone.utc).isoformat()
    batch = [
        {
            "event_id": "evt_dup1",
            "sensor_id": "S001",
            "machine_id": "M01",
            "event_timestamp": now_iso,
            "temperature_celsius": 42.0,
        },
        {
            "event_id": "evt_dup1",  # duplicate event_id
            "sensor_id": "S001",
            "machine_id": "M01",
            "event_timestamp": now_iso,
            "temperature_celsius": 42.0,
        },
        {
            "event_id": "evt_valid2",
            "sensor_id": "S002",
            "machine_id": "M01",
            "event_timestamp": now_iso,
            "temperature_celsius": 48.0,
        },
    ]
    valid, rejected = validator.validate_batch(batch)
    assert len(valid) == 2
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "DUPLICATE_EVENT_ID_IN_BATCH"
