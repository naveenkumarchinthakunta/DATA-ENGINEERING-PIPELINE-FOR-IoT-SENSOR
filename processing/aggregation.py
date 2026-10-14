"""
Analytical Aggregation and Statistics Engine.
Calculates real-time KPIs, machine-level rollups, sensor freshness, and multi-scale
time-window summaries (1m, 5m, 15m, 1h) from processed telemetry and pipeline tables.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
from storage.models import (
    Sensor,
    RawSensorData,
    ProcessedSensorData,
    RejectedSensorData,
    MachineHealthAlert,
    PipelineRun,
)
from config.settings import settings


class AnalyticsEngine:
    """
    Executes analytical queries and window aggregations over the database.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_overall_summary(
        self, reporting_window_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculates high-level system KPIs:
        Sensor activity, data quality success/rejection rates, record counts, and global telemetry averages.
        """
        window_mins = (
            reporting_window_minutes
            if reporting_window_minutes is not None
            else settings.quality.reporting_window_minutes
        )
        cutoff_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=window_mins)

        # Total registered sensors
        total_sensors = self.session.query(func.count(Sensor.sensor_id)).scalar() or 0

        # Active sensors: distinct sensors reporting at or after cutoff_time
        active_sensor_ids = {
            row[0]
            for row in self.session.query(ProcessedSensorData.sensor_id)
            .filter(ProcessedSensorData.event_timestamp >= cutoff_time)
            .distinct()
            .all()
        }
        active_count = len(active_sensor_ids)
        inactive_count = max(0, total_sensors - active_count)

        # Record counts
        raw_count = self.session.query(func.count(RawSensorData.event_id)).scalar() or 0
        processed_count = (
            self.session.query(func.count(ProcessedSensorData.event_id)).scalar() or 0
        )
        rejected_count = (
            self.session.query(func.count(RejectedSensorData.rejection_id)).scalar() or 0
        )

        total_evaluated = processed_count + rejected_count
        success_rate = (
            round((processed_count / total_evaluated) * 100.0, 2)
            if total_evaluated > 0
            else 100.0
        )
        rejection_rate = (
            round((rejected_count / total_evaluated) * 100.0, 2)
            if total_evaluated > 0
            else 0.0
        )

        # Measurements statistics
        stats = (
            self.session.query(
                func.avg(ProcessedSensorData.temperature_celsius),
                func.min(ProcessedSensorData.temperature_celsius),
                func.max(ProcessedSensorData.temperature_celsius),
                func.avg(ProcessedSensorData.pressure_bar),
                func.min(ProcessedSensorData.pressure_bar),
                func.max(ProcessedSensorData.pressure_bar),
                func.avg(ProcessedSensorData.vibration_mm_s),
                func.min(ProcessedSensorData.vibration_mm_s),
                func.max(ProcessedSensorData.vibration_mm_s),
            )
            .first()
        )

        # Alert counts
        total_alerts = (
            self.session.query(func.count(MachineHealthAlert.alert_id)).scalar() or 0
        )
        active_alerts = (
            self.session.query(func.count(MachineHealthAlert.alert_id))
            .filter(MachineHealthAlert.alert_status == "ACTIVE")
            .scalar()
            or 0
        )

        # Pipeline runs
        pipeline_runs_count = (
            self.session.query(func.count(PipelineRun.run_id)).scalar() or 0
        )
        successful_runs = (
            self.session.query(func.count(PipelineRun.run_id))
            .filter(PipelineRun.execution_status == "COMPLETED")
            .scalar()
            or 0
        )
        pipeline_success_rate = (
            round((successful_runs / pipeline_runs_count) * 100.0, 2)
            if pipeline_runs_count > 0
            else 100.0
        )

        # Last successful run time
        last_run = (
            self.session.query(PipelineRun)
            .filter(PipelineRun.execution_status == "COMPLETED")
            .order_by(desc(PipelineRun.end_timestamp))
            .first()
        )

        return {
            "total_registered_sensors": total_sensors,
            "active_sensors": active_count,
            "inactive_sensors": inactive_count,
            "reporting_window_minutes": window_mins,
            "total_raw_records": raw_count,
            "total_processed_records": processed_count,
            "total_rejected_records": rejected_count,
            "validation_success_rate": success_rate,
            "data_rejection_rate": rejection_rate,
            "temperature_stats": {
                "avg": round(stats[0], 2) if stats and stats[0] is not None else 0.0,
                "min": round(stats[1], 2) if stats and stats[1] is not None else 0.0,
                "max": round(stats[2], 2) if stats and stats[2] is not None else 0.0,
            },
            "pressure_stats": {
                "avg": round(stats[3], 2) if stats and stats[3] is not None else 0.0,
                "min": round(stats[4], 2) if stats and stats[4] is not None else 0.0,
                "max": round(stats[5], 2) if stats and stats[5] is not None else 0.0,
            },
            "vibration_stats": {
                "avg": round(stats[6], 2) if stats and stats[6] is not None else 0.0,
                "min": round(stats[7], 2) if stats and stats[7] is not None else 0.0,
                "max": round(stats[8], 2) if stats and stats[8] is not None else 0.0,
            },
            "total_alerts": total_alerts,
            "active_alerts": active_alerts,
            "pipeline_runs_count": pipeline_runs_count,
            "pipeline_success_rate": pipeline_success_rate,
            "last_successful_run": (
                last_run.end_timestamp.isoformat() if last_run and last_run.end_timestamp else None
            ),
        }

    def get_machine_summary(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """Calculates aggregated metrics for a specific machine."""
        readings = (
            self.session.query(ProcessedSensorData)
            .filter(ProcessedSensorData.machine_id == machine_id)
            .all()
        )
        if not readings:
            return None

        temps = [r.temperature_celsius for r in readings if r.temperature_celsius is not None]
        press = [r.pressure_bar for r in readings if r.pressure_bar is not None]
        vibs = [r.vibration_mm_s for r in readings if r.vibration_mm_s is not None]

        alerts_count = (
            self.session.query(func.count(MachineHealthAlert.alert_id))
            .filter(MachineHealthAlert.machine_id == machine_id)
            .scalar()
            or 0
        )

        return {
            "machine_id": machine_id,
            "total_readings": len(readings),
            "temperature": {
                "avg": round(float(np.mean(temps)), 2) if temps else 0.0,
                "min": round(float(np.min(temps)), 2) if temps else 0.0,
                "max": round(float(np.max(temps)), 2) if temps else 0.0,
                "std": round(float(np.std(temps)), 2) if len(temps) > 1 else 0.0,
            },
            "pressure": {
                "avg": round(float(np.mean(press)), 2) if press else 0.0,
                "min": round(float(np.min(press)), 2) if press else 0.0,
                "max": round(float(np.max(press)), 2) if press else 0.0,
                "std": round(float(np.std(press)), 2) if len(press) > 1 else 0.0,
            },
            "vibration": {
                "avg": round(float(np.mean(vibs)), 2) if vibs else 0.0,
                "min": round(float(np.min(vibs)), 2) if vibs else 0.0,
                "max": round(float(np.max(vibs)), 2) if vibs else 0.0,
                "std": round(float(np.std(vibs)), 2) if len(vibs) > 1 else 0.0,
            },
            "total_alerts": alerts_count,
        }

    def get_time_window_aggregations(
        self,
        sensor_id: Optional[str] = None,
        machine_id: Optional[str] = None,
        window: str = "5min",
    ) -> List[Dict[str, Any]]:
        """
        Aggregates telemetry across configurable time windows (1min, 5min, 15min, 1hour).
        Calculates count, avg, min, max, std dev.
        """
        query = self.session.query(ProcessedSensorData)
        if sensor_id:
            query = query.filter(ProcessedSensorData.sensor_id == sensor_id)
        if machine_id:
            query = query.filter(ProcessedSensorData.machine_id == machine_id)

        rows = query.order_by(ProcessedSensorData.event_timestamp).all()
        if not rows:
            return []

        # Convert to pandas DataFrame for time-bucket resampling
        data = [
            {
                "event_timestamp": r.event_timestamp,
                "temperature": r.temperature_celsius,
                "pressure": r.pressure_bar,
                "vibration": r.vibration_mm_s,
            }
            for r in rows
        ]
        df = pd.DataFrame(data)
        df.set_index("event_timestamp", inplace=True)

        rule_map = {
            "1min": "1min",
            "5min": "5min",
            "15min": "15min",
            "1hour": "1h",
            "1h": "1h",
        }
        resample_rule = rule_map.get(window, "5min")

        grouped = df.resample(resample_rule)
        agg_df = grouped.agg({
            "temperature": ["count", "mean", "min", "max", "std"],
            "pressure": ["mean", "min", "max"],
            "vibration": ["mean", "min", "max"],
        }).dropna(subset=[("temperature", "count")])

        results = []
        for index, row in agg_df.iterrows():
            if row[("temperature", "count")] == 0:
                continue
            results.append({
                "window_start": index.isoformat(),
                "readings_count": int(row[("temperature", "count")]),
                "temperature_avg": round(float(row[("temperature", "mean")]), 2) if pd.notna(row[("temperature", "mean")]) else None,
                "temperature_min": round(float(row[("temperature", "min")]), 2) if pd.notna(row[("temperature", "min")]) else None,
                "temperature_max": round(float(row[("temperature", "max")]), 2) if pd.notna(row[("temperature", "max")]) else None,
                "temperature_std": round(float(row[("temperature", "std")]), 2) if pd.notna(row[("temperature", "std")]) else 0.0,
                "pressure_avg": round(float(row[("pressure", "mean")]), 2) if pd.notna(row[("pressure", "mean")]) else None,
                "pressure_min": round(float(row[("pressure", "min")]), 2) if pd.notna(row[("pressure", "min")]) else None,
                "pressure_max": round(float(row[("pressure", "max")]), 2) if pd.notna(row[("pressure", "max")]) else None,
                "vibration_avg": round(float(row[("vibration", "mean")]), 2) if pd.notna(row[("vibration", "mean")]) else None,
                "vibration_min": round(float(row[("vibration", "min")]), 2) if pd.notna(row[("vibration", "min")]) else None,
                "vibration_max": round(float(row[("vibration", "max")]), 2) if pd.notna(row[("vibration", "max")]) else None,
            })

        return results
