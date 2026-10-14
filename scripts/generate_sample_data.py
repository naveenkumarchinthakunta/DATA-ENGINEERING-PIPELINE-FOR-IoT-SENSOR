"""
Sample Data Generator Script.
Populates the database with multi-cycle historical sensor readings,
staggered timestamps, operational anomalies, and quarantined records.
"""

from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.database import init_db
from pipeline.pipeline_runner import PipelineRunner
from simulator.sensor_simulator import SensorSimulator
from monitoring.logging_config import logger


def generate_history(num_batches: int = 5):
    init_db()
    simulator = SensorSimulator()
    runner = PipelineRunner(simulator=simulator)

    logger.info("Generating %d historical batches for 200 sensors...", num_batches)
    now = datetime.now(timezone.utc)

    for i in range(num_batches, 0, -1):
        batch_time = now - timedelta(minutes=i * 2)
        logger.info("Generating batch for time: %s", batch_time.isoformat())
        records = simulator.generate_batch(timestamp=batch_time)
        summary = runner.run_cycle(input_records=records)
        print(f"Batch {num_batches - i + 1}/{num_batches}: {summary.records_processed} processed, {summary.records_rejected} quarantined, {summary.alerts_generated} alerts.")

    print(f"Successfully generated historical telemetry across {num_batches} cycles.")


if __name__ == "__main__":
    generate_history(num_batches=5)
