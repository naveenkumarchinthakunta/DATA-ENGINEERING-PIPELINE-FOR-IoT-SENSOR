"""
Database Initialization Script.
Creates all schema tables and synchronizes the 200 sensor registry metadata records.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.database import init_db, get_db_session
from pipeline.pipeline_runner import PipelineRunner
from monitoring.logging_config import logger


def main():
    logger.info("Initializing IoT Data Pipeline database...")
    init_db()

    logger.info("Synchronizing sensor metadata (200 sensors)...")
    runner = PipelineRunner()
    with get_db_session() as session:
        synced_count = runner.sync_sensor_metadata(session)
    logger.info("Successfully registered/synchronized %d IoT sensors.", synced_count)
    print(f"Database initialized and {synced_count} sensors registered successfully.")


if __name__ == "__main__":
    main()
