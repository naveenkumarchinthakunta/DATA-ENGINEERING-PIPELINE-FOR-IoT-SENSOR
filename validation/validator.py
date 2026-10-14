"""
Data Validation Engine for IoT Sensor Readings.
Performs structural, schema, and data quality validation.
Separates valid records from quarantined/rejected records, preserving full audit lineage.
Strictly distinguishes between Data Quality Failures (corrupted/malformed records)
and Operational Anomalies (physically extreme but structurally valid sensor measurements).
"""

from datetime import datetime, timezone, timedelta
import math
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field, ValidationError, field_validator
from config.settings import settings
from monitoring.logging_config import logger


class SensorReadingSchema(BaseModel):
    """Pydantic schema for structural and data type verification."""
    event_id: str = Field(..., min_length=1)
    sensor_id: str = Field(..., min_length=1)
    machine_id: str = Field(..., min_length=1)
    factory_zone: Optional[str] = "Unknown"
    event_timestamp: str = Field(..., min_length=1)
    temperature_celsius: Optional[float] = None
    pressure_bar: Optional[float] = None
    vibration_mm_s: Optional[float] = None

    @field_validator("temperature_celsius", "pressure_bar", "vibration_mm_s", mode="before")
    @classmethod
    def check_non_null_number(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            if math.isnan(v) or math.isinf(v):
                raise ValueError("Measurement cannot be NaN or Infinite")
            return float(v)
        # Attempt conversion if numeric string
        try:
            val = float(v)
            if math.isnan(val) or math.isinf(val):
                raise ValueError("Measurement cannot be NaN or Infinite")
            return val
        except (ValueError, TypeError):
            raise ValueError(f"Measurement must be a valid number, got {v}")


class ValidationOutcome:
    def __init__(
        self,
        is_valid: bool,
        record: Dict[str, Any],
        rejection_reason: Optional[str] = None,
        errors: List[str] = None,
    ):
        self.is_valid = is_valid
        self.record = record
        self.rejection_reason = rejection_reason
        self.errors = errors or []


class DataValidator:
    """
    Validates sensor telemetry records according to enterprise data quality standards.
    """

    def __init__(self, max_future_skew_seconds: Optional[int] = None):
        self.max_future_skew_seconds = (
            max_future_skew_seconds
            if max_future_skew_seconds is not None
            else settings.quality.max_future_skew_seconds
        )

    def validate_record(self, raw_record: Dict[str, Any]) -> ValidationOutcome:
        """
        Validates an individual sensor record.
        Returns ValidationOutcome indicating validity, parsed record, or rejection reason.
        """
        if not isinstance(raw_record, dict):
            return ValidationOutcome(
                is_valid=False,
                record=raw_record if isinstance(raw_record, dict) else {},
                rejection_reason="INVALID_STRUCTURE_NOT_A_DICT",
                errors=["Payload is not a dictionary"],
            )

        event_id = raw_record.get("event_id")
        sensor_id = raw_record.get("sensor_id")

        # 1. Structural schema validation via Pydantic
        try:
            validated_model = SensorReadingSchema(**raw_record)
        except ValidationError as ve:
            errors = [f"{err['loc']}: {err['msg']}" for err in ve.errors()]
            reason = "SCHEMA_VALIDATION_ERROR: " + "; ".join(errors)
            return ValidationOutcome(
                is_valid=False,
                record=raw_record,
                rejection_reason=reason[:250],
                errors=errors,
            )

        # 2. Timestamp sanity check (ISO parsing and future skew validation)
        ts_str = validated_model.event_timestamp
        try:
            clean_ts = ts_str.replace("Z", "+00:00")
            parsed_dt = datetime.fromisoformat(clean_ts)
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            else:
                parsed_dt = parsed_dt.astimezone(timezone.utc)
        except Exception as e:
            return ValidationOutcome(
                is_valid=False,
                record=raw_record,
                rejection_reason=f"MALFORMED_TIMESTAMP: {str(e)}",
                errors=[f"Could not parse timestamp '{ts_str}'"],
            )

        # Check for unrealistic future timestamp (e.g. clock desynchronization or corrupted event)
        current_utc = datetime.now(timezone.utc)
        allowed_future_bound = current_utc + timedelta(seconds=self.max_future_skew_seconds)
        if parsed_dt > allowed_future_bound:
            return ValidationOutcome(
                is_valid=False,
                record=raw_record,
                rejection_reason=f"FUTURE_TIMESTAMP_EXCEEDED_SKEW: event={parsed_dt.isoformat()}, now={current_utc.isoformat()}",
                errors=["Timestamp is set too far in the future"],
            )

        # 3. Check for completeness of measurement fields
        # Note: In our industrial setup, at least one measurement must be present
        if (
            validated_model.temperature_celsius is None
            and validated_model.pressure_bar is None
            and validated_model.vibration_mm_s is None
        ):
            return ValidationOutcome(
                is_valid=False,
                record=raw_record,
                rejection_reason="ALL_MEASUREMENTS_NULL",
                errors=["All measurement fields are null"],
            )

        # 4. Physical possibility limits (structural sanity check, not operational limits)
        # e.g., absolute zero in Celsius is -273.15; negative absolute pressure is physical nonsense
        if (
            validated_model.temperature_celsius is not None
            and validated_model.temperature_celsius < -273.15
        ):
            return ValidationOutcome(
                is_valid=False,
                record=raw_record,
                rejection_reason="TEMPERATURE_BELOW_ABSOLUTE_ZERO",
                errors=["Temperature violates physical laws (< -273.15 C)"],
            )

        if (
            validated_model.pressure_bar is not None
            and validated_model.pressure_bar < 0.0
        ):
            return ValidationOutcome(
                is_valid=False,
                record=raw_record,
                rejection_reason="NEGATIVE_ABSOLUTE_PRESSURE",
                errors=["Pressure cannot be negative in absolute bar"],
            )

        if (
            validated_model.vibration_mm_s is not None
            and validated_model.vibration_mm_s < 0.0
        ):
            return ValidationOutcome(
                is_valid=False,
                record=raw_record,
                rejection_reason="NEGATIVE_VIBRATION_VALUE",
                errors=["Vibration amplitude cannot be negative"],
            )

        # Record is structurally valid!
        clean_dict = validated_model.model_dump()
        clean_dict["parsed_event_timestamp"] = parsed_dt.replace(tzinfo=None)
        return ValidationOutcome(
            is_valid=True,
            record=clean_dict,
        )

    def validate_batch(
        self, records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validates a batch of records.
        Deduplicates within the incoming batch.
        Returns:
            (valid_records, rejected_records)
        """
        valid_records: List[Dict[str, Any]] = []
        rejected_records: List[Dict[str, Any]] = []
        seen_event_ids = set()

        for rec in records:
            event_id = rec.get("event_id") if isinstance(rec, dict) else None

            # Intra-batch duplicate check
            if event_id and event_id in seen_event_ids:
                rejected_records.append({
                    "event_id": event_id,
                    "sensor_id": rec.get("sensor_id"),
                    "raw_payload": rec,
                    "rejection_reason": "DUPLICATE_EVENT_ID_IN_BATCH",
                    "rejection_timestamp": datetime.now(timezone.utc).replace(tzinfo=None),
                })
                continue

            outcome = self.validate_record(rec)
            if outcome.is_valid:
                valid_records.append(outcome.record)
                if event_id:
                    seen_event_ids.add(event_id)
            else:
                rejected_records.append({
                    "event_id": event_id,
                    "sensor_id": rec.get("sensor_id") if isinstance(rec, dict) else None,
                    "raw_payload": rec,
                    "rejection_reason": outcome.rejection_reason,
                    "rejection_timestamp": datetime.now(timezone.utc).replace(tzinfo=None),
                })

        logger.info(
            "Validation complete: %d valid, %d rejected",
            len(valid_records),
            len(rejected_records),
        )
        return valid_records, rejected_records
