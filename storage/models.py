"""
SQLAlchemy ORM models defining the relational database schema for the IoT Data Pipeline.
Includes tables for sensor metadata, raw records, processed records, rejected/quarantine records,
machine health alerts, and pipeline execution tracking.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    DateTime,
    Text,
    Index,
    UniqueConstraint,
)
from storage.database import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Sensor(Base):
    """Stores sensor registry metadata, operating thresholds, and factory zone mapping."""
    __tablename__ = "sensors"

    sensor_id = Column(String(50), primary_key=True)
    machine_id = Column(String(50), nullable=False, index=True)
    factory_zone = Column(String(50), nullable=False, index=True)
    sensor_status = Column(String(20), nullable=False, default="ACTIVE")  # ACTIVE, INACTIVE, MAINTENANCE
    temperature_limit_min = Column(Float, nullable=False, default=20.0)
    temperature_limit_max = Column(Float, nullable=False, default=85.0)
    pressure_limit_min = Column(Float, nullable=False, default=1.0)
    pressure_limit_max = Column(Float, nullable=False, default=10.0)
    vibration_limit_min = Column(Float, nullable=False, default=0.0)
    vibration_limit_max = Column(Float, nullable=False, default=5.0)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "machine_id": self.machine_id,
            "factory_zone": self.factory_zone,
            "sensor_status": self.sensor_status,
            "temperature_limit_min": self.temperature_limit_min,
            "temperature_limit_max": self.temperature_limit_max,
            "pressure_limit_min": self.pressure_limit_min,
            "pressure_limit_max": self.pressure_limit_max,
            "vibration_limit_min": self.vibration_limit_min,
            "vibration_limit_max": self.vibration_limit_max,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RawSensorData(Base):
    """Stores original ingested sensor records before validation or transformation."""
    __tablename__ = "raw_sensor_data"

    event_id = Column(String(100), primary_key=True)
    sensor_id = Column(String(50), nullable=False, index=True)
    event_timestamp = Column(DateTime, nullable=False, index=True)
    ingestion_timestamp = Column(DateTime, nullable=False, index=True, default=utc_now)
    raw_payload = Column(Text, nullable=False)
    ingestion_status = Column(String(30), nullable=False, default="RECEIVED")  # RECEIVED, DUPLICATE, FAILED

    __table_args__ = (
        Index("idx_raw_sensor_time", "sensor_id", "event_timestamp"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "sensor_id": self.sensor_id,
            "event_timestamp": self.event_timestamp.isoformat() if self.event_timestamp else None,
            "ingestion_timestamp": self.ingestion_timestamp.isoformat() if self.ingestion_timestamp else None,
            "raw_payload": self.raw_payload,
            "ingestion_status": self.ingestion_status,
        }


class ProcessedSensorData(Base):
    """Stores validated, standardized, and transformed sensor records ready for analytical querying."""
    __tablename__ = "processed_sensor_data"

    event_id = Column(String(100), primary_key=True)
    sensor_id = Column(String(50), nullable=False, index=True)
    machine_id = Column(String(50), nullable=False, index=True)
    event_timestamp = Column(DateTime, nullable=False, index=True)
    temperature_celsius = Column(Float, nullable=True)
    pressure_bar = Column(Float, nullable=True)
    vibration_mm_s = Column(Float, nullable=True)
    validation_status = Column(String(20), nullable=False, default="VALID")
    transformation_timestamp = Column(DateTime, nullable=False, default=utc_now)
    quality_flags = Column(Text, nullable=True)  # JSON or comma-separated string of flags/features

    __table_args__ = (
        Index("idx_processed_sensor_time", "sensor_id", "event_timestamp"),
        Index("idx_processed_machine_time", "machine_id", "event_timestamp"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "sensor_id": self.sensor_id,
            "machine_id": self.machine_id,
            "event_timestamp": self.event_timestamp.isoformat() if self.event_timestamp else None,
            "temperature_celsius": self.temperature_celsius,
            "pressure_bar": self.pressure_bar,
            "vibration_mm_s": self.vibration_mm_s,
            "validation_status": self.validation_status,
            "transformation_timestamp": (
                self.transformation_timestamp.isoformat() if self.transformation_timestamp else None
            ),
            "quality_flags": self.quality_flags,
        }


class RejectedSensorData(Base):
    """Quarantine table for records failing structural or data quality checks."""
    __tablename__ = "rejected_sensor_data"

    rejection_id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(100), nullable=True, index=True)
    sensor_id = Column(String(50), nullable=True, index=True)
    raw_payload = Column(Text, nullable=False)
    rejection_reason = Column(Text, nullable=False)
    rejection_timestamp = Column(DateTime, nullable=False, default=utc_now)

    __table_args__ = (
        Index("idx_rejected_time", "rejection_timestamp"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rejection_id": self.rejection_id,
            "event_id": self.event_id,
            "sensor_id": self.sensor_id,
            "raw_payload": self.raw_payload,
            "rejection_reason": self.rejection_reason,
            "rejection_timestamp": (
                self.rejection_timestamp.isoformat() if self.rejection_timestamp else None
            ),
        }


class MachineHealthAlert(Base):
    """Operational anomaly alerts generated when valid readings cross operating thresholds."""
    __tablename__ = "machine_health_alerts"

    alert_id = Column(String(100), primary_key=True)
    sensor_id = Column(String(50), nullable=False, index=True)
    machine_id = Column(String(50), nullable=False, index=True)
    event_id = Column(String(100), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)  # TEMP_HIGH, TEMP_LOW, PRESSURE_HIGH, VIBRATION_SPIKE, etc.
    severity = Column(String(20), nullable=False)    # WARNING, CRITICAL, INFO
    measured_value = Column(Float, nullable=True)
    configured_threshold = Column(Float, nullable=True)
    alert_timestamp = Column(DateTime, nullable=False, default=utc_now, index=True)
    alert_status = Column(String(20), nullable=False, default="ACTIVE")  # ACTIVE, ACKNOWLEDGED, RESOLVED

    __table_args__ = (
        Index("idx_alerts_machine_time", "machine_id", "alert_timestamp"),
        UniqueConstraint("event_id", "alert_type", name="uq_event_alert_type"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "sensor_id": self.sensor_id,
            "machine_id": self.machine_id,
            "event_id": self.event_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "measured_value": self.measured_value,
            "configured_threshold": self.configured_threshold,
            "alert_timestamp": self.alert_timestamp.isoformat() if self.alert_timestamp else None,
            "alert_status": self.alert_status,
        }


class PipelineRun(Base):
    """Tracks execution cycles, stage metrics, records counts, and pipeline health."""
    __tablename__ = "pipeline_runs"

    run_id = Column(String(100), primary_key=True)
    start_timestamp = Column(DateTime, nullable=False, default=utc_now)
    end_timestamp = Column(DateTime, nullable=True)
    execution_status = Column(String(30), nullable=False, default="RUNNING")  # RUNNING, COMPLETED, FAILED, PARTIAL
    records_received = Column(Integer, nullable=False, default=0)
    records_processed = Column(Integer, nullable=False, default=0)
    records_rejected = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    execution_summary = Column(Text, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "start_timestamp": self.start_timestamp.isoformat() if self.start_timestamp else None,
            "end_timestamp": self.end_timestamp.isoformat() if self.end_timestamp else None,
            "execution_status": self.execution_status,
            "records_received": self.records_received,
            "records_processed": self.records_processed,
            "records_rejected": self.records_rejected,
            "error_count": self.error_count,
            "execution_summary": self.execution_summary,
        }
