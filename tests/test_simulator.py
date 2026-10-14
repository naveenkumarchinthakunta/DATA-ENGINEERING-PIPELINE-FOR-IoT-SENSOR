"""
Unit tests for Sensor Simulator.
"""

import pytest
from simulator.sensor_simulator import SensorSimulator


def test_sensor_metadata_generation():
    sim = SensorSimulator(total_sensors=200, total_machines=20)
    sensors = sim.get_registered_sensors()

    assert len(sensors) == 200
    assert sensors[0]["sensor_id"] == "S001"
    assert sensors[-1]["sensor_id"] == "S200"

    # Check machine assignments
    machine_ids = {s["machine_id"] for s in sensors}
    assert len(machine_ids) == 20
    assert "M01" in machine_ids
    assert "M20" in machine_ids

    # Check limits
    for s in sensors:
        assert s["temperature_limit_min"] < s["temperature_limit_max"]
        assert s["pressure_limit_min"] < s["pressure_limit_max"]
        assert s["vibration_limit_min"] < s["vibration_limit_max"]


def test_deterministic_generation_with_seed():
    sim1 = SensorSimulator(total_sensors=10, seed=42)
    sim2 = SensorSimulator(total_sensors=10, seed=42)

    batch1 = sim1.generate_batch(batch_size=10, include_duplicates=False)
    batch2 = sim2.generate_batch(batch_size=10, include_duplicates=False)

    assert len(batch1) == len(batch2)
    for r1, r2 in zip(batch1, batch2):
        assert r1["sensor_id"] == r2["sensor_id"]
        assert r1["temperature_celsius"] == r2["temperature_celsius"]
        assert r1["pressure_bar"] == r2["pressure_bar"]


def test_single_reading_fields():
    sim = SensorSimulator(total_sensors=5, seed=10)
    sensor_meta = sim.get_registered_sensors()[0]
    reading = sim.generate_single_reading(sensor_meta)

    assert "event_id" in reading
    assert reading["sensor_id"] == sensor_meta["sensor_id"]
    assert reading["machine_id"] == sensor_meta["machine_id"]
    assert "event_timestamp" in reading
    assert "ingestion_timestamp" in reading
    assert isinstance(reading["temperature_celsius"], float)
    assert isinstance(reading["pressure_bar"], float)
    assert isinstance(reading["vibration_mm_s"], float)
    assert reading["is_simulated"] is True
