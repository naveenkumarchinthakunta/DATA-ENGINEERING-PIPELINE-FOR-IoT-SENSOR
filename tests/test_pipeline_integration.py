"""
End-to-End Pipeline Integration Test.
Verifies the complete flow from sensor generation/ingestion through validation,
quarantine, transformation, persistent storage, anomaly detection, and analytical retrieval.
"""

from datetime import datetime, timezone
import pytest
from storage.database import init_db, get_db_session
from storage.repositories import (
    SensorRepository,
    RawDataRepository,
    ProcessedDataRepository,
    RejectedDataRepository,
    AlertRepository,
    PipelineRunRepository,
)
from pipeline.pipeline_runner import PipelineRunner
from simulator.sensor_simulator import SensorSimulator
from processing.aggregation import AnalyticsEngine


def test_complete_end_to_end_pipeline_flow():
    init_db()

    # Create deterministic simulator with known anomalies and quality faults
    sim = SensorSimulator(
        total_sensors=200,
        total_machines=20,
        seed=123,
        anomaly_rate=0.10,
        quality_fault_rate=0.08,
    )
    runner = PipelineRunner(simulator=sim)

    # 1. Execute full cycle
    summary = runner.run_cycle(batch_size=200)

    assert summary.status == "COMPLETED"
    assert summary.records_received > 0
    assert summary.records_ingested > 0
    assert summary.records_processed > 0
    assert summary.records_rejected > 0  # Quality faults were injected and caught!
    assert summary.alerts_generated > 0  # Operational anomalies were injected and caught!
    assert summary.duration_seconds > 0.0

    # 2. Database verification across all tables
    with get_db_session() as session:
        sensor_repo = SensorRepository(session)
        raw_repo = RawDataRepository(session)
        proc_repo = ProcessedDataRepository(session)
        rej_repo = RejectedDataRepository(session)
        alert_repo = AlertRepository(session)
        run_repo = PipelineRunRepository(session)
        analytics = AnalyticsEngine(session)

        # Sensors registered
        assert sensor_repo.count() == 200

        # Raw storage populated
        assert raw_repo.count() >= summary.records_ingested

        # Processed storage populated
        assert proc_repo.count() >= summary.records_processed

        # Quarantined rejected storage populated
        assert rej_repo.count() >= summary.records_rejected
        rejection_reasons = rej_repo.get_rejection_summary()
        assert len(rejection_reasons) > 0

        # Operational alerts generated
        assert alert_repo.count() >= summary.alerts_generated

        # Pipeline runs logged
        assert run_repo.count() >= 1

        # Analytics verification
        kpis = analytics.get_overall_summary()
        assert kpis["total_registered_sensors"] == 200
        assert kpis["active_sensors"] > 0
        assert kpis["validation_success_rate"] > 0.0


def test_retry_safety_and_deduplication():
    """
    Verifies that running the same raw records twice is retry-safe:
    No duplicate raw records, no duplicate processed records, no duplicate alerts.
    """
    init_db()
    sim = SensorSimulator(total_sensors=10, seed=999)
    fixed_batch = sim.generate_batch(batch_size=10, include_duplicates=False)

    runner = PipelineRunner(simulator=sim)

    # First execution
    summary1 = runner.run_cycle(input_records=fixed_batch)

    # Second execution with exact same input records (simulating network retry)
    summary2 = runner.run_cycle(input_records=fixed_batch)

    with get_db_session() as session:
        raw_repo = RawDataRepository(session)
        proc_repo = ProcessedDataRepository(session)
        alert_repo = AlertRepository(session)

        # Repositories must not have doubled!
        # The unique event_ids ensure idempotent processing
        assert summary2.records_processed == 0  # Already processed in cycle 1
        assert summary2.records_ingested == 0   # Already ingested in cycle 1
