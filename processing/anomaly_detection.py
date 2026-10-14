"""
Rule-Based Machine Health Anomaly Detection Engine.
Identifies operational anomalies against configurable per-machine/sensor operating limits.
Emits structured machine health alerts (WARNING, CRITICAL, INFO) with traceability
to the originating event, measured values, and exact thresholds violated.
"""

from datetime import datetime, timezone
import json
import uuid
from typing import List, Dict, Any, Optional
from config.settings import settings
from monitoring.logging_config import logger


class AnomalyDetector:
    """
    Evaluates transformed sensor telemetry against machine-specific operating thresholds
    and temporal rate-of-change limits.
    """

    def __init__(self, sensor_limits: Optional[Dict[str, Dict[str, float]]] = None):
        """
        sensor_limits: Map of sensor_id -> {
            'temperature_limit_min', 'temperature_limit_max',
            'pressure_limit_min', 'pressure_limit_max',
            'vibration_limit_min', 'vibration_limit_max'
        }
        """
        self.sensor_limits = sensor_limits or {}

    def set_limits(self, limits: Dict[str, Dict[str, float]]) -> None:
        self.sensor_limits = limits

    def evaluate_record(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluates an individual processed record and returns any triggered alerts.
        """
        alerts = []
        sensor_id = record["sensor_id"]
        machine_id = record["machine_id"]
        event_id = record["event_id"]
        event_ts = record["event_timestamp"]
        temp = record.get("temperature_celsius")
        press = record.get("pressure_bar")
        vib = record.get("vibration_mm_s")

        # Threshold configuration for this sensor, with global fallback
        limits = self.sensor_limits.get(sensor_id, {})
        t_min = limits.get("temperature_limit_min", settings.quality.default_temp_min)
        t_max = limits.get("temperature_limit_max", settings.quality.default_temp_max)
        p_min = limits.get("pressure_limit_min", settings.quality.default_pressure_min)
        p_max = limits.get("pressure_limit_max", settings.quality.default_pressure_max)
        v_min = limits.get("vibration_limit_min", settings.quality.default_vibration_min)
        v_max = limits.get("vibration_limit_max", settings.quality.default_vibration_max)

        # 1. Temperature checks
        if temp is not None:
            if temp > t_max:
                severity = "CRITICAL" if temp > (t_max + 10.0) else "WARNING"
                alerts.append({
                    "alert_id": f"alt_{uuid.uuid4().hex[:12]}",
                    "sensor_id": sensor_id,
                    "machine_id": machine_id,
                    "event_id": event_id,
                    "alert_type": "TEMP_HIGH",
                    "severity": severity,
                    "measured_value": temp,
                    "configured_threshold": t_max,
                    "alert_timestamp": event_ts,
                    "alert_status": "ACTIVE",
                })
            elif temp < t_min:
                alerts.append({
                    "alert_id": f"alt_{uuid.uuid4().hex[:12]}",
                    "sensor_id": sensor_id,
                    "machine_id": machine_id,
                    "event_id": event_id,
                    "alert_type": "TEMP_LOW",
                    "severity": "WARNING",
                    "measured_value": temp,
                    "configured_threshold": t_min,
                    "alert_timestamp": event_ts,
                    "alert_status": "ACTIVE",
                })

        # 2. Pressure checks
        if press is not None:
            if press > p_max:
                severity = "CRITICAL" if press > (p_max + 2.0) else "WARNING"
                alerts.append({
                    "alert_id": f"alt_{uuid.uuid4().hex[:12]}",
                    "sensor_id": sensor_id,
                    "machine_id": machine_id,
                    "event_id": event_id,
                    "alert_type": "PRESSURE_HIGH",
                    "severity": severity,
                    "measured_value": press,
                    "configured_threshold": p_max,
                    "alert_timestamp": event_ts,
                    "alert_status": "ACTIVE",
                })
            elif press < p_min:
                alerts.append({
                    "alert_id": f"alt_{uuid.uuid4().hex[:12]}",
                    "sensor_id": sensor_id,
                    "machine_id": machine_id,
                    "event_id": event_id,
                    "alert_type": "PRESSURE_LOW",
                    "severity": "WARNING",
                    "measured_value": press,
                    "configured_threshold": p_min,
                    "alert_timestamp": event_ts,
                    "alert_status": "ACTIVE",
                })

        # 3. Vibration checks
        if vib is not None:
            if vib > v_max:
                severity = "CRITICAL" if vib > (v_max + 2.0) else "WARNING"
                alerts.append({
                    "alert_id": f"alt_{uuid.uuid4().hex[:12]}",
                    "sensor_id": sensor_id,
                    "machine_id": machine_id,
                    "event_id": event_id,
                    "alert_type": "VIBRATION_SPIKE",
                    "severity": severity,
                    "measured_value": vib,
                    "configured_threshold": v_max,
                    "alert_timestamp": event_ts,
                    "alert_status": "ACTIVE",
                })

        # 4. Sudden Rate of Change checks (from quality_flags if present)
        quality_flags_str = record.get("quality_flags")
        if quality_flags_str:
            try:
                flags = (
                    json.loads(quality_flags_str)
                    if isinstance(quality_flags_str, str)
                    else quality_flags_str
                )
                temp_roc = flags.get("temp_rate_of_change_per_sec")
                if temp_roc and abs(temp_roc) > settings.quality.temp_rate_of_change_threshold:
                    alerts.append({
                        "alert_id": f"alt_{uuid.uuid4().hex[:12]}",
                        "sensor_id": sensor_id,
                        "machine_id": machine_id,
                        "event_id": event_id,
                        "alert_type": "TEMP_RATE_SPIKE",
                        "severity": "WARNING",
                        "measured_value": round(temp_roc, 2),
                        "configured_threshold": settings.quality.temp_rate_of_change_threshold,
                        "alert_timestamp": event_ts,
                        "alert_status": "ACTIVE",
                    })
            except Exception:
                pass

        return alerts

    def evaluate_batch(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Evaluates a batch of processed records and collects all detected operational anomalies.
        """
        all_alerts = []
        for rec in records:
            all_alerts.extend(self.evaluate_record(rec))

        if all_alerts:
            logger.warning(
                "Anomaly detection triggered %d operational alerts across %d processed events",
                len(all_alerts),
                len(records),
            )
        return all_alerts
