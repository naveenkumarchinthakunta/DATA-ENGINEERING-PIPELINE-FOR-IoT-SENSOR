"""
Unit tests for Data Transformation Engine.
"""

from datetime import datetime, timezone, timedelta
import json
import pytest
from transformation.transformer import DataTransformer


def test_transformation_baseline_deviation():
    baselines = {
        "S001": {
            "temperature_limit_min": 20.0,
            "temperature_limit_max": 80.0,  # mid baseline = 50.0
            "pressure_limit_min": 2.0,
            "pressure_limit_max": 6.0,   # mid baseline = 4.0
        }
    }
    transformer = DataTransformer(sensor_baselines=baselines)

    now_dt = datetime.now(timezone.utc)
    record = {
        "event_id": "evt_tr1",
        "sensor_id": "s001",  # Test lower-to-upper normalization
        "machine_id": "m01",
        "event_timestamp": now_dt.isoformat(),
        "temperature_celsius": 55.0,
        "pressure_bar": 4.5,
        "vibration_mm_s": 1.5,
    }

    transformed = transformer.transform_record(record)
    assert transformed["sensor_id"] == "S001"
    assert transformed["machine_id"] == "M01"
    assert transformed["temperature_celsius"] == 55.0
    assert transformed["pressure_bar"] == 4.5

    flags = json.loads(transformed["quality_flags"])
    assert flags["temp_deviation"] == 5.0  # 55.0 - 50.0
    assert flags["press_deviation"] == 0.5  # 4.5 - 4.0


def test_rate_of_change_between_consecutive_readings():
    transformer = DataTransformer()
    t0 = datetime(2026, 10, 13, 10, 0, 0)
    t1 = datetime(2026, 10, 13, 10, 0, 5)  # 5 seconds later

    r1 = {
        "event_id": "evt_seq1",
        "sensor_id": "S010",
        "machine_id": "M02",
        "event_timestamp": t0.isoformat(),
        "parsed_event_timestamp": t0,
        "temperature_celsius": 50.0,
        "pressure_bar": 4.0,
        "vibration_mm_s": 1.0,
    }
    r2 = {
        "event_id": "evt_seq2",
        "sensor_id": "S010",
        "machine_id": "M02",
        "event_timestamp": t1.isoformat(),
        "parsed_event_timestamp": t1,
        "temperature_celsius": 60.0,  # +10 C over 5s = 2.0 C/s
        "pressure_bar": 5.0,
        "vibration_mm_s": 1.0,
    }

    transformer.transform_record(r1)
    res2 = transformer.transform_record(r2)

    flags = json.loads(res2["quality_flags"])
    assert flags["seconds_since_last_event"] == 5.0
    assert flags["temp_rate_of_change_per_sec"] == 2.0


def test_preservation_of_none_values():
    transformer = DataTransformer()
    record = {
        "event_id": "evt_tr_null",
        "sensor_id": "S005",
        "machine_id": "M01",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_celsius": None,
        "pressure_bar": 3.2,
        "vibration_mm_s": None,
    }
    transformed = transformer.transform_record(record)
    # Strictly preserve None; do not convert to 0.0
    assert transformed["temperature_celsius"] is None
    assert transformed["vibration_mm_s"] is None
    assert transformed["pressure_bar"] == 3.2
