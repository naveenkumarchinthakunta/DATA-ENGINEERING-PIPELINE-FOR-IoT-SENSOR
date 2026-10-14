"""
Unit tests for Analytics Aggregations and Anomaly Detection.
"""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from storage.database import Base
from storage.models import Sensor, ProcessedSensorData, RejectedSensorData, RawSensorData
from processing.aggregation import AnalyticsEngine
from processing.anomaly_detection import AnomalyDetector


@pytest.fixture
def analytics_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()

    # Populate sample sensor
    sensor = Sensor(
        sensor_id="S001",
        machine_id="M01",
        factory_zone="Zone-North",
        sensor_status="ACTIVE",
    )
    session.add(sensor)

    # Populate 3 processed records with known values
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    records = [
        ProcessedSensorData(
            event_id="e1",
            sensor_id="S001",
            machine_id="M01",
            event_timestamp=now - timedelta(minutes=2),
            temperature_celsius=50.0,
            pressure_bar=4.0,
            vibration_mm_s=1.0,
        ),
        ProcessedSensorData(
            event_id="e2",
            sensor_id="S001",
            machine_id="M01",
            event_timestamp=now - timedelta(minutes=1),
            temperature_celsius=60.0,
            pressure_bar=5.0,
            vibration_mm_s=2.0,
        ),
        ProcessedSensorData(
            event_id="e3",
            sensor_id="S001",
            machine_id="M01",
            event_timestamp=now,
            temperature_celsius=70.0,
            pressure_bar=6.0,
            vibration_mm_s=3.0,
        ),
    ]
    session.add_all(records)
    session.commit()

    yield session
    session.close()


def test_analytics_kpi_summary(analytics_session):
    engine = AnalyticsEngine(analytics_session)
    summary = engine.get_overall_summary(reporting_window_minutes=5)

    assert summary["total_registered_sensors"] == 1
    assert summary["active_sensors"] == 1
    assert summary["inactive_sensors"] == 0
    assert summary["total_processed_records"] == 3
    assert summary["temperature_stats"]["avg"] == 60.0  # (50 + 60 + 70) / 3
    assert summary["temperature_stats"]["min"] == 50.0
    assert summary["temperature_stats"]["max"] == 70.0


def test_analytics_machine_summary(analytics_session):
    engine = AnalyticsEngine(analytics_session)
    mach = engine.get_machine_summary("M01")

    assert mach is not None
    assert mach["machine_id"] == "M01"
    assert mach["total_readings"] == 3
    assert mach["temperature"]["avg"] == 60.0
    assert mach["pressure"]["avg"] == 5.0
    assert mach["vibration"]["avg"] == 2.0


def test_anomaly_detection_thresholds():
    limits = {
        "S001": {
            "temperature_limit_min": 20.0,
            "temperature_limit_max": 80.0,
            "pressure_limit_min": 1.0,
            "pressure_limit_max": 8.0,
            "vibration_limit_min": 0.0,
            "vibration_limit_max": 4.0,
        }
    }
    detector = AnomalyDetector(sensor_limits=limits)
    now_dt = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Normal record - no alerts
    normal_rec = {
        "event_id": "e_norm",
        "sensor_id": "S001",
        "machine_id": "M01",
        "event_timestamp": now_dt,
        "temperature_celsius": 50.0,
        "pressure_bar": 4.0,
        "vibration_mm_s": 2.0,
    }
    assert len(detector.evaluate_record(normal_rec)) == 0

    # 2. Critical temperature spike (exceeds max + 10 = 90)
    hot_rec = {
        "event_id": "e_hot",
        "sensor_id": "S001",
        "machine_id": "M01",
        "event_timestamp": now_dt,
        "temperature_celsius": 95.0,
        "pressure_bar": 4.0,
        "vibration_mm_s": 2.0,
    }
    hot_alerts = detector.evaluate_record(hot_rec)
    assert len(hot_alerts) == 1
    assert hot_alerts[0]["alert_type"] == "TEMP_HIGH"
    assert hot_alerts[0]["severity"] == "CRITICAL"
    assert hot_alerts[0]["measured_value"] == 95.0

    # 3. Vibration warning (exceeds 4.0 but <= 6.0)
    vib_rec = {
        "event_id": "e_vib",
        "sensor_id": "S001",
        "machine_id": "M01",
        "event_timestamp": now_dt,
        "temperature_celsius": 50.0,
        "pressure_bar": 4.0,
        "vibration_mm_s": 4.8,
    }
    vib_alerts = detector.evaluate_record(vib_rec)
    assert len(vib_alerts) == 1
    assert vib_alerts[0]["alert_type"] == "VIBRATION_SPIKE"
    assert vib_alerts[0]["severity"] == "WARNING"
