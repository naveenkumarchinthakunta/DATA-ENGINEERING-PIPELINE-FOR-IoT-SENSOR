"""
Repository layer providing clean, transactional, and parameterized database access.
Implements bounded query patterns, pagination, and idempotent batch operations.
"""

from datetime import datetime, timezone
import json
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, text
from sqlalchemy.exc import IntegrityError
from storage.models import (
    Sensor,
    RawSensorData,
    ProcessedSensorData,
    RejectedSensorData,
    MachineHealthAlert,
    PipelineRun,
    utc_now,
)
from monitoring.logging_config import logger


class SensorRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(
        self, factory_zone: Optional[str] = None, status: Optional[str] = None
    ) -> List[Sensor]:
        query = self.session.query(Sensor)
        if factory_zone:
            query = query.filter(Sensor.factory_zone == factory_zone)
        if status:
            query = query.filter(Sensor.sensor_status == status)
        return query.order_by(Sensor.sensor_id).all()

    def get_by_id(self, sensor_id: str) -> Optional[Sensor]:
        return self.session.query(Sensor).filter(Sensor.sensor_id == sensor_id).first()

    def count(self) -> int:
        return self.session.query(func.count(Sensor.sensor_id)).scalar() or 0

    def upsert_sensors(self, sensors_data: List[Dict[str, Any]]) -> int:
        count = 0
        for item in sensors_data:
            sensor = self.get_by_id(item["sensor_id"])
            if not sensor:
                sensor = Sensor(
                    sensor_id=item["sensor_id"],
                    machine_id=item["machine_id"],
                    factory_zone=item["factory_zone"],
                    sensor_status=item.get("sensor_status", "ACTIVE"),
                    temperature_limit_min=item.get("temperature_limit_min", 20.0),
                    temperature_limit_max=item.get("temperature_limit_max", 85.0),
                    pressure_limit_min=item.get("pressure_limit_min", 1.0),
                    pressure_limit_max=item.get("pressure_limit_max", 10.0),
                    vibration_limit_min=item.get("vibration_limit_min", 0.0),
                    vibration_limit_max=item.get("vibration_limit_max", 5.0),
                )
                self.session.add(sensor)
            else:
                sensor.machine_id = item["machine_id"]
                sensor.factory_zone = item["factory_zone"]
                sensor.sensor_status = item.get("sensor_status", sensor.sensor_status)
                sensor.temperature_limit_min = item.get("temperature_limit_min", sensor.temperature_limit_min)
                sensor.temperature_limit_max = item.get("temperature_limit_max", sensor.temperature_limit_max)
                sensor.pressure_limit_min = item.get("pressure_limit_min", sensor.pressure_limit_min)
                sensor.pressure_limit_max = item.get("pressure_limit_max", sensor.pressure_limit_max)
                sensor.vibration_limit_min = item.get("vibration_limit_min", sensor.vibration_limit_min)
                sensor.vibration_limit_max = item.get("vibration_limit_max", sensor.vibration_limit_max)
                sensor.updated_at = utc_now()
            count += 1
        return count


class RawDataRepository:
    def __init__(self, session: Session):
        self.session = session

    def exists(self, event_id: str) -> bool:
        return (
            self.session.query(RawSensorData.event_id)
            .filter(RawSensorData.event_id == event_id)
            .first()
            is not None
        )

    def save_batch(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Inserts raw sensor events.
        Returns: (inserted_count, duplicate_count)
        """
        if not records:
            return 0, 0

        # Identify existing event_ids in incoming batch
        event_ids = [r["event_id"] for r in records if "event_id" in r and r["event_id"]]
        existing_ids = set()
        if event_ids:
            found = (
                self.session.query(RawSensorData.event_id)
                .filter(RawSensorData.event_id.in_(event_ids))
                .all()
            )
            existing_ids = {row[0] for row in found}

        inserted = 0
        duplicates = 0

        for r in records:
            event_id = r.get("event_id")
            if not event_id or event_id in existing_ids:
                duplicates += 1
                continue

            raw_payload = r.get("raw_payload")
            if not isinstance(raw_payload, str):
                raw_payload = json.dumps(raw_payload)

            raw_record = RawSensorData(
                event_id=event_id,
                sensor_id=r.get("sensor_id", "UNKNOWN"),
                event_timestamp=r["event_timestamp"],
                ingestion_timestamp=r.get("ingestion_timestamp", utc_now()),
                raw_payload=raw_payload,
                ingestion_status=r.get("ingestion_status", "RECEIVED"),
            )
            self.session.add(raw_record)
            existing_ids.add(event_id)
            inserted += 1

        return inserted, duplicates

    def count(self) -> int:
        return self.session.query(func.count(RawSensorData.event_id)).scalar() or 0


class ProcessedDataRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_batch(self, records: List[Dict[str, Any]]) -> int:
        """
        Idempotently inserts processed sensor records.
        """
        if not records:
            return 0

        event_ids = [r["event_id"] for r in records if "event_id" in r]
        existing_ids = set()
        if event_ids:
            found = (
                self.session.query(ProcessedSensorData.event_id)
                .filter(ProcessedSensorData.event_id.in_(event_ids))
                .all()
            )
            existing_ids = {row[0] for row in found}

        inserted = 0
        for r in records:
            event_id = r["event_id"]
            if event_id in existing_ids:
                continue

            quality_flags = r.get("quality_flags")
            if isinstance(quality_flags, (dict, list)):
                quality_flags = json.dumps(quality_flags)

            proc_record = ProcessedSensorData(
                event_id=event_id,
                sensor_id=r["sensor_id"],
                machine_id=r["machine_id"],
                event_timestamp=r["event_timestamp"],
                temperature_celsius=r.get("temperature_celsius"),
                pressure_bar=r.get("pressure_bar"),
                vibration_mm_s=r.get("vibration_mm_s"),
                validation_status=r.get("validation_status", "VALID"),
                transformation_timestamp=r.get("transformation_timestamp", utc_now()),
                quality_flags=quality_flags,
            )
            self.session.add(proc_record)
            existing_ids.add(event_id)
            inserted += 1

        return inserted

    def count(self) -> int:
        return self.session.query(func.count(ProcessedSensorData.event_id)).scalar() or 0

    def get_readings_by_sensor(
        self,
        sensor_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Tuple[List[ProcessedSensorData], int]:
        query = self.session.query(ProcessedSensorData).filter(
            ProcessedSensorData.sensor_id == sensor_id
        )
        if start_time:
            query = query.filter(ProcessedSensorData.event_timestamp >= start_time)
        if end_time:
            query = query.filter(ProcessedSensorData.event_timestamp <= end_time)

        total = query.count()
        results = (
            query.order_by(desc(ProcessedSensorData.event_timestamp))
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return results, total

    def get_recent_readings(self, limit: int = 100) -> List[ProcessedSensorData]:
        return (
            self.session.query(ProcessedSensorData)
            .order_by(desc(ProcessedSensorData.event_timestamp))
            .limit(limit)
            .all()
        )


class RejectedDataRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_batch(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0

        inserted = 0
        for r in records:
            raw_payload = r.get("raw_payload")
            if not isinstance(raw_payload, str):
                raw_payload = json.dumps(raw_payload)

            rejected_rec = RejectedSensorData(
                event_id=r.get("event_id"),
                sensor_id=r.get("sensor_id"),
                raw_payload=raw_payload,
                rejection_reason=r.get("rejection_reason", "UNKNOWN_ERROR"),
                rejection_timestamp=r.get("rejection_timestamp", utc_now()),
            )
            self.session.add(rejected_rec)
            inserted += 1

        return inserted

    def count(self) -> int:
        return self.session.query(func.count(RejectedSensorData.rejection_id)).scalar() or 0

    def get_rejection_summary(self) -> List[Dict[str, Any]]:
        results = (
            self.session.query(
                RejectedSensorData.rejection_reason,
                func.count(RejectedSensorData.rejection_id).label("count"),
            )
            .group_by(RejectedSensorData.rejection_reason)
            .order_by(desc("count"))
            .all()
        )
        return [{"reason": row[0], "count": row[1]} for row in results]

    def get_recent_rejections(self, limit: int = 50) -> List[RejectedSensorData]:
        return (
            self.session.query(RejectedSensorData)
            .order_by(desc(RejectedSensorData.rejection_timestamp))
            .limit(limit)
            .all()
        )


class AlertRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_batch(self, alerts: List[Dict[str, Any]]) -> int:
        if not alerts:
            return 0

        inserted = 0
        for a in alerts:
            # Check unique constraint (event_id, alert_type)
            existing = (
                self.session.query(MachineHealthAlert.alert_id)
                .filter(
                    MachineHealthAlert.event_id == a["event_id"],
                    MachineHealthAlert.alert_type == a["alert_type"],
                )
                .first()
            )
            if existing:
                continue

            alert = MachineHealthAlert(
                alert_id=a["alert_id"],
                sensor_id=a["sensor_id"],
                machine_id=a["machine_id"],
                event_id=a["event_id"],
                alert_type=a["alert_type"],
                severity=a["severity"],
                measured_value=a.get("measured_value"),
                configured_threshold=a.get("configured_threshold"),
                alert_timestamp=a.get("alert_timestamp", utc_now()),
                alert_status=a.get("alert_status", "ACTIVE"),
            )
            self.session.add(alert)
            inserted += 1

        return inserted

    def count(self) -> int:
        return self.session.query(func.count(MachineHealthAlert.alert_id)).scalar() or 0

    def get_alerts(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        machine_id: Optional[str] = None,
        sensor_id: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Tuple[List[MachineHealthAlert], int]:
        query = self.session.query(MachineHealthAlert)
        if severity:
            query = query.filter(MachineHealthAlert.severity == severity)
        if status:
            query = query.filter(MachineHealthAlert.alert_status == status)
        if machine_id:
            query = query.filter(MachineHealthAlert.machine_id == machine_id)
        if sensor_id:
            query = query.filter(MachineHealthAlert.sensor_id == sensor_id)

        total = query.count()
        results = (
            query.order_by(desc(MachineHealthAlert.alert_timestamp))
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return results, total

    def acknowledge_alert(self, alert_id: str) -> bool:
        alert = (
            self.session.query(MachineHealthAlert)
            .filter(MachineHealthAlert.alert_id == alert_id)
            .first()
        )
        if alert:
            alert.alert_status = "ACKNOWLEDGED"
            return True
        return False

    def get_counts_by_severity(self) -> Dict[str, int]:
        results = (
            self.session.query(
                MachineHealthAlert.severity,
                func.count(MachineHealthAlert.alert_id),
            )
            .group_by(MachineHealthAlert.severity)
            .all()
        )
        return {row[0]: row[1] for row in results}


class PipelineRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_run(self, run_id: str, start_timestamp: datetime) -> PipelineRun:
        run = PipelineRun(
            run_id=run_id,
            start_timestamp=start_timestamp,
            execution_status="RUNNING",
        )
        self.session.add(run)
        return run

    def finish_run(
        self,
        run_id: str,
        execution_status: str,
        records_received: int,
        records_processed: int,
        records_rejected: int,
        error_count: int,
        execution_summary: str,
    ) -> Optional[PipelineRun]:
        run = self.session.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if run:
            run.end_timestamp = utc_now()
            run.execution_status = execution_status
            run.records_received = records_received
            run.records_processed = records_processed
            run.records_rejected = records_rejected
            run.error_count = error_count
            run.execution_summary = execution_summary
        return run

    def get_recent_runs(self, limit: int = 20) -> List[PipelineRun]:
        return (
            self.session.query(PipelineRun)
            .order_by(desc(PipelineRun.start_timestamp))
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        return self.session.query(func.count(PipelineRun.run_id)).scalar() or 0
