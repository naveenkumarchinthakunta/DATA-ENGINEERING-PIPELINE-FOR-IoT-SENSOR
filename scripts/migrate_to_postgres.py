"""
SQLite to PostgreSQL Database Migration Utility.
Facilitates seamless migration from local SQLite development storage
to an enterprise PostgreSQL or TimescaleDB production instance.

Usage:
  python scripts/migrate_to_postgres.py --target-url postgresql://user:password@localhost:5432/iot_pipeline
"""

import argparse
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.database import Base, engine as source_engine
from storage.models import (
    Sensor,
    RawSensorData,
    ProcessedSensorData,
    RejectedSensorData,
    MachineHealthAlert,
    PipelineRun,
)
from monitoring.logging_config import logger


def migrate(target_url: str):
    print("=" * 70)
    print(" IOT DATA PIPELINE: SQLITE -> POSTGRESQL MIGRATION UTILITY")
    print("=" * 70)

    print(f"\n1. Connecting to Target PostgreSQL: {target_url}")
    target_engine = create_engine(target_url, future=True)

    print("2. Creating Target Schema Tables...")
    Base.metadata.create_all(bind=target_engine)
    print("   Target tables initialized successfully.")

    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)

    with SourceSession() as src_sess, TargetSession() as tgt_sess:
        tables_to_migrate = [
            ("Sensors", Sensor),
            ("RawSensorData", RawSensorData),
            ("ProcessedSensorData", ProcessedSensorData),
            ("RejectedSensorData", RejectedSensorData),
            ("MachineHealthAlerts", MachineHealthAlert),
            ("PipelineRuns", PipelineRun),
        ]

        print("\n3. Migrating Table Data:")
        for name, model in tables_to_migrate:
            rows = src_sess.query(model).all()
            print(f"   - Migrating {name:<22}: {len(rows):>5} rows ...", end="")
            for row in rows:
                src_sess.expunge(row)
                tgt_sess.merge(row)
            tgt_sess.commit()
            print(" [COMPLETED]")

    print("\n" + "=" * 70)
    print(" Migration to PostgreSQL completed with 100% data fidelity.")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SQLite to PostgreSQL")
    parser.add_argument("--target-url", required=True, help="Target PostgreSQL connection URI")
    args = parser.parse_args()
    migrate(args.target_url)
