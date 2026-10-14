"""
Data Ingestion Service for IoT Sensor telemetry.
Receives incoming payloads, applies pre-ingestion structural sanity checks,
attaches standardized UTC ingestion timestamps, and writes raw payloads to persistent storage.
Tracks received, accepted, duplicate, and failed counts idempotently.
"""

from datetime import datetime, timezone
import json
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from storage.repositories import RawDataRepository
from monitoring.logging_config import logger


class IngestionResult:
    def __init__(
        self,
        received: int = 0,
        accepted: int = 0,
        duplicates: int = 0,
        failed: int = 0,
        errors: List[str] = None,
    ):
        self.received = received
        self.accepted = accepted
        self.duplicates = duplicates
        self.failed = failed
        self.errors = errors or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "received": self.received,
            "accepted": self.accepted,
            "duplicates": self.duplicates,
            "failed": self.failed,
            "errors": self.errors,
        }


class IngestionService:
    """
    Handles ingestion of single or batched IoT sensor records into the raw storage layer.
    """

    def __init__(self, raw_repo: RawDataRepository):
        self.raw_repo = raw_repo

    def ingest_record(self, record: Dict[str, Any]) -> IngestionResult:
        """Ingests a single sensor record."""
        return self.ingest_batch([record])

    def ingest_batch(self, records: List[Dict[str, Any]]) -> IngestionResult:
        """
        Ingests a batch of records into raw storage.
        Preserves raw payloads for lineage and reprocessing.
        """
        result = IngestionResult(received=len(records))
        if not records:
            return result

        valid_raw_entries = []
        now_utc = datetime.now(timezone.utc)

        for idx, rec in enumerate(records):
            if not isinstance(rec, dict):
                result.failed += 1
                result.errors.append(f"Record at index {idx} is not a valid JSON dictionary")
                continue

            event_id = rec.get("event_id")
            if not event_id:
                result.failed += 1
                result.errors.append(f"Record at index {idx} missing required 'event_id'")
                continue

            sensor_id = rec.get("sensor_id", "UNKNOWN")

            # Parse event_timestamp or default to current UTC if absent
            raw_ts = rec.get("event_timestamp")
            if raw_ts:
                try:
                    if isinstance(raw_ts, str):
                        # Normalize ISO string
                        ts_clean = raw_ts.replace("Z", "+00:00")
                        event_dt = datetime.fromisoformat(ts_clean)
                    elif isinstance(raw_ts, datetime):
                        event_dt = raw_ts
                    else:
                        event_dt = now_utc
                except Exception:
                    event_dt = now_utc
            else:
                event_dt = now_utc

            # Ensure event_dt is naive or standardized for DB
            if event_dt.tzinfo is not None:
                event_dt = event_dt.astimezone(timezone.utc).replace(tzinfo=None)

            valid_raw_entries.append({
                "event_id": str(event_id),
                "sensor_id": str(sensor_id),
                "event_timestamp": event_dt,
                "ingestion_timestamp": now_utc.replace(tzinfo=None),
                "raw_payload": rec,
                "ingestion_status": "RECEIVED",
            })

        # Save to database repository
        try:
            inserted, dups = self.raw_repo.save_batch(valid_raw_entries)
            result.accepted += inserted
            result.duplicates += dups
            logger.info(
                "Ingestion batch complete: received=%d, accepted=%d, duplicates=%d, failed=%d",
                result.received,
                result.accepted,
                result.duplicates,
                result.failed,
            )
        except Exception as e:
            logger.error("Failed persisting raw ingestion batch: %s", e)
            result.failed += len(valid_raw_entries)
            result.errors.append(f"Persistence error: {str(e)}")

        return result
