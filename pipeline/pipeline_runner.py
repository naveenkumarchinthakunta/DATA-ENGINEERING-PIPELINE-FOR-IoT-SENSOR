"""
Pipeline Orchestration Engine.
Coordinates data flow across ingestion, validation, quarantine, transformation,
persistence, anomaly evaluation, and pipeline run auditing.
Provides transaction management, error recovery boundaries, and execution status tracking.
"""

from datetime import datetime, timezone
import json
import time
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from storage.database import get_db_session
from storage.repositories import (
    SensorRepository,
    RawDataRepository,
    ProcessedDataRepository,
    RejectedDataRepository,
    AlertRepository,
    PipelineRunRepository,
)
from simulator.sensor_simulator import SensorSimulator
from ingestion.ingestion_service import IngestionService
from validation.validator import DataValidator
from transformation.transformer import DataTransformer
from processing.anomaly_detection import AnomalyDetector
from config.settings import settings
from monitoring.logging_config import logger


class PipelineExecutionSummary:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.status = "RUNNING"
        self.records_received = 0
        self.records_ingested = 0
        self.records_processed = 0
        self.records_rejected = 0
        self.alerts_generated = 0
        self.error_count = 0
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        self.duration_seconds = 0.0
        self.stage_timings: Dict[str, float] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "records_received": self.records_received,
            "records_ingested": self.records_ingested,
            "records_processed": self.records_processed,
            "records_rejected": self.records_rejected,
            "alerts_generated": self.alerts_generated,
            "error_count": self.error_count,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "stage_timings": self.stage_timings,
        }


class PipelineRunner:
    """
    Coordinates end-to-end execution of the IoT data pipeline.
    """

    def __init__(self, simulator: Optional[SensorSimulator] = None):
        self.simulator = simulator or SensorSimulator()
        self.validator = DataValidator()
        self.transformer = DataTransformer()
        self.anomaly_detector = AnomalyDetector()

    def sync_sensor_metadata(self, session: Session) -> int:
        """
        Synchronizes sensor registry in the database with simulator metadata.
        Returns count of synced sensors.
        """
        sensor_repo = SensorRepository(session)
        sensors = self.simulator.get_registered_sensors()
        synced = sensor_repo.upsert_sensors(sensors)

        # Configure transformer and anomaly detector with latest limits
        baselines = {
            s["sensor_id"]: {
                "temperature_limit_min": s["temperature_limit_min"],
                "temperature_limit_max": s["temperature_limit_max"],
                "pressure_limit_min": s["pressure_limit_min"],
                "pressure_limit_max": s["pressure_limit_max"],
                "vibration_limit_min": s["vibration_limit_min"],
                "vibration_limit_max": s["vibration_limit_max"],
            }
            for s in sensors
        }
        self.transformer.set_baselines(baselines)
        self.anomaly_detector.set_limits(baselines)
        return synced

    def run_cycle(
        self,
        input_records: Optional[List[Dict[str, Any]]] = None,
        batch_size: Optional[int] = None,
    ) -> PipelineExecutionSummary:
        """
        Executes a single end-to-end pipeline run cycle.
        If input_records is not provided, generates a batch via the sensor simulator.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        summary = PipelineExecutionSummary(run_id)
        logger.info("=== Starting Pipeline Run Cycle: %s ===", run_id)

        with get_db_session() as session:
            run_repo = PipelineRunRepository(session)
            raw_repo = RawDataRepository(session)
            proc_repo = ProcessedDataRepository(session)
            rej_repo = RejectedDataRepository(session)
            alert_repo = AlertRepository(session)

            # Record initial pipeline run in DB
            run_repo.create_run(run_id, summary.start_time.replace(tzinfo=None))
            session.commit()

            try:
                # Ensure sensor metadata is up to date
                self.sync_sensor_metadata(session)

                # STAGE 1: Data Acquisition / Generation
                t0 = time.perf_counter()
                if input_records is not None:
                    records = input_records
                else:
                    records = self.simulator.generate_batch(batch_size=batch_size)
                summary.stage_timings["generation_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                summary.records_received = len(records)

                # STAGE 2: Ingestion & Raw Persistence
                t0 = time.perf_counter()
                ingestion_service = IngestionService(raw_repo)
                ingest_res = ingestion_service.ingest_batch(records)
                summary.records_ingested = ingest_res.accepted
                summary.stage_timings["ingestion_ms"] = round((time.perf_counter() - t0) * 1000, 2)

                # STAGE 3: Data Validation
                t0 = time.perf_counter()
                valid_records, rejected_records = self.validator.validate_batch(records)
                summary.records_rejected = len(rejected_records)
                summary.stage_timings["validation_ms"] = round((time.perf_counter() - t0) * 1000, 2)

                # Persist Rejected Records (Quarantine Storage)
                if rejected_records:
                    rej_repo.save_batch(rejected_records)

                # STAGE 4: Transformation
                t0 = time.perf_counter()
                transformed_records = self.transformer.transform_batch(valid_records)
                summary.stage_timings["transformation_ms"] = round((time.perf_counter() - t0) * 1000, 2)

                # Persist Processed Data
                t0 = time.perf_counter()
                inserted_proc = proc_repo.save_batch(transformed_records)
                summary.records_processed = inserted_proc
                summary.stage_timings["persistence_ms"] = round((time.perf_counter() - t0) * 1000, 2)

                # STAGE 5: Anomaly Detection
                t0 = time.perf_counter()
                alerts = self.anomaly_detector.evaluate_batch(transformed_records)
                if alerts:
                    alert_repo.save_batch(alerts)
                summary.alerts_generated = len(alerts)
                summary.stage_timings["anomaly_detection_ms"] = round((time.perf_counter() - t0) * 1000, 2)

                # Finish run status
                summary.status = "COMPLETED"
                summary.end_time = datetime.now(timezone.utc)
                summary.duration_seconds = round(
                    (summary.end_time - summary.start_time).total_seconds(), 3
                )

                run_repo.finish_run(
                    run_id=run_id,
                    execution_status=summary.status,
                    records_received=summary.records_received,
                    records_processed=summary.records_processed,
                    records_rejected=summary.records_rejected,
                    error_count=summary.error_count,
                    execution_summary=json.dumps(summary.to_dict()),
                )
                logger.info(
                    "Pipeline run %s COMPLETED in %.3fs: Ingested=%d, Processed=%d, Rejected=%d, Alerts=%d",
                    run_id,
                    summary.duration_seconds,
                    summary.records_ingested,
                    summary.records_processed,
                    summary.records_rejected,
                    summary.alerts_generated,
                )

            except Exception as e:
                summary.status = "FAILED"
                summary.error_count += 1
                summary.end_time = datetime.now(timezone.utc)
                summary.duration_seconds = round(
                    (summary.end_time - summary.start_time).total_seconds(), 3
                )
                logger.error("Pipeline run %s FAILED: %s", run_id, e, exc_info=True)
                run_repo.finish_run(
                    run_id=run_id,
                    execution_status="FAILED",
                    records_received=summary.records_received,
                    records_processed=summary.records_processed,
                    records_rejected=summary.records_rejected,
                    error_count=summary.error_count,
                    execution_summary=f"Execution error: {str(e)}",
                )
                raise

        return summary
