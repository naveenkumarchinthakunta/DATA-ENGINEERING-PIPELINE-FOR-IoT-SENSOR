"""
REST API Blueprint for IoT Sensor Data Pipeline.
Exposes endpoints for health checks, sensor registry, telemetry readings,
machine aggregations, alerts, data quality metrics, and pipeline runs.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify
from storage.database import get_db_session, check_db_health
from storage.repositories import (
    SensorRepository,
    ProcessedDataRepository,
    RejectedDataRepository,
    AlertRepository,
    PipelineRunRepository,
)
from processing.aggregation import AnalyticsEngine
from pipeline.pipeline_runner import PipelineRunner
from monitoring.logging_config import logger

api_bp = Blueprint("api", __name__, url_prefix="/api")


def success_response(data: Any, message: str = "Success", status_code: int = 200):
    return jsonify({
        "status": "success",
        "message": message,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), status_code


def error_response(message: str, error_code: str = "BAD_REQUEST", status_code: int = 400):
    return jsonify({
        "status": "error",
        "error_code": error_code,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), status_code


@api_bp.route("/health", methods=["GET"])
def health_check():
    """Health check for service and database connectivity."""
    db_healthy = check_db_health()
    status_str = "HEALTHY" if db_healthy else "UNHEALTHY"
    status_code = 200 if db_healthy else 503
    return success_response({
        "application_status": status_str,
        "database_connected": db_healthy,
        "environment": "production-ready local",
    }, message=f"Service is {status_str}", status_code=status_code)


@api_bp.route("/sensors", methods=["GET"])
def get_sensors():
    """Returns registered sensors with optional filtering by factory_zone or status."""
    zone = request.args.get("zone")
    status = request.args.get("status")

    with get_db_session() as session:
        repo = SensorRepository(session)
        sensors = repo.get_all(factory_zone=zone, status=status)
        return success_response({
            "total": len(sensors),
            "sensors": [s.to_dict() for s in sensors],
        })


@api_bp.route("/sensors/<sensor_id>/readings", methods=["GET"])
def get_sensor_readings(sensor_id: str):
    """Returns historical readings for a sensor with optional time filters and pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 500)
    start_time_str = request.args.get("start_time")
    end_time_str = request.args.get("end_time")

    start_dt = None
    end_dt = None
    try:
        if start_time_str:
            start_dt = datetime.fromisoformat(start_time_str.replace("Z", "+00:00")).replace(tzinfo=None)
        if end_time_str:
            end_dt = datetime.fromisoformat(end_time_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception as e:
        return error_response(f"Invalid timestamp format: {e}", "INVALID_TIMESTAMP", 400)

    with get_db_session() as session:
        # Check if sensor exists
        sensor_repo = SensorRepository(session)
        sensor = sensor_repo.get_by_id(sensor_id)
        if not sensor:
            return error_response(f"Sensor '{sensor_id}' not found", "NOT_FOUND", 404)

        proc_repo = ProcessedDataRepository(session)
        readings, total = proc_repo.get_readings_by_sensor(
            sensor_id, start_time=start_dt, end_time=end_dt, page=page, per_page=per_page
        )
        return success_response({
            "sensor_id": sensor_id,
            "page": page,
            "per_page": per_page,
            "total_records": total,
            "readings": [r.to_dict() for r in readings],
        })


@api_bp.route("/machines/<machine_id>/summary", methods=["GET"])
def get_machine_summary(machine_id: str):
    """Returns machine-level aggregated statistics and sensor metrics."""
    with get_db_session() as session:
        analytics = AnalyticsEngine(session)
        summary = analytics.get_machine_summary(machine_id)
        if not summary:
            return error_response(f"No records found for machine '{machine_id}'", "NOT_FOUND", 404)
        return success_response(summary)


@api_bp.route("/analytics/summary", methods=["GET"])
def get_analytics_summary():
    """Returns overall factory analytics, KPI cards, and quality statistics."""
    window_mins = request.args.get("window_minutes", type=int)
    with get_db_session() as session:
        analytics = AnalyticsEngine(session)
        summary = analytics.get_overall_summary(reporting_window_minutes=window_mins)
        return success_response(summary)


@api_bp.route("/analytics/window", methods=["GET"])
def get_window_aggregations():
    """Returns multi-scale time-window rollups (1min, 5min, 15min, 1hour)."""
    sensor_id = request.args.get("sensor_id")
    machine_id = request.args.get("machine_id")
    window = request.args.get("window", "5min")

    with get_db_session() as session:
        analytics = AnalyticsEngine(session)
        results = analytics.get_time_window_aggregations(
            sensor_id=sensor_id, machine_id=machine_id, window=window
        )
        return success_response({
            "window": window,
            "sensor_id": sensor_id,
            "machine_id": machine_id,
            "total_windows": len(results),
            "aggregations": results,
        })


@api_bp.route("/alerts", methods=["GET"])
def get_alerts():
    """Returns operational machine health alerts with filtering and pagination."""
    severity = request.args.get("severity")
    status = request.args.get("status")
    machine_id = request.args.get("machine_id")
    sensor_id = request.args.get("sensor_id")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)

    with get_db_session() as session:
        alert_repo = AlertRepository(session)
        alerts, total = alert_repo.get_alerts(
            severity=severity,
            status=status,
            machine_id=machine_id,
            sensor_id=sensor_id,
            page=page,
            per_page=per_page,
        )
        severity_counts = alert_repo.get_counts_by_severity()
        return success_response({
            "page": page,
            "per_page": per_page,
            "total_alerts": total,
            "severity_breakdown": severity_counts,
            "alerts": [a.to_dict() for a in alerts],
        })


@api_bp.route("/alerts/<alert_id>/acknowledge", methods=["POST"])
def acknowledge_alert(alert_id: str):
    """Marks an active alert as acknowledged."""
    with get_db_session() as session:
        alert_repo = AlertRepository(session)
        success = alert_repo.acknowledge_alert(alert_id)
        if not success:
            return error_response(f"Alert '{alert_id}' not found", "NOT_FOUND", 404)
        return success_response({"alert_id": alert_id, "status": "ACKNOWLEDGED"})


@api_bp.route("/pipeline/runs", methods=["GET"])
def get_pipeline_runs():
    """Returns recent pipeline execution history and stage status."""
    limit = min(request.args.get("limit", 20, type=int), 100)
    with get_db_session() as session:
        run_repo = PipelineRunRepository(session)
        runs = run_repo.get_recent_runs(limit=limit)
        return success_response({
            "total_runs_returned": len(runs),
            "runs": [r.to_dict() for r in runs],
        })


@api_bp.route("/pipeline/trigger", methods=["POST"])
def trigger_pipeline():
    """Triggers an on-demand pipeline execution cycle."""
    data = request.get_json(silent=True) or {}
    batch_size = data.get("batch_size")

    runner = PipelineRunner()
    try:
        summary = runner.run_cycle(batch_size=batch_size)
        return success_response(summary.to_dict(), message="Pipeline cycle executed successfully")
    except Exception as e:
        return error_response(f"Pipeline execution failed: {str(e)}", "PIPELINE_ERROR", 500)


@api_bp.route("/data-quality/summary", methods=["GET"])
def get_data_quality_summary():
    """Returns validation statistics, quarantined records count, and failure categorization."""
    with get_db_session() as session:
        rej_repo = RejectedDataRepository(session)
        rejection_summary = rej_repo.get_rejection_summary()
        recent_rejections = rej_repo.get_recent_rejections(limit=20)
        total_rejected = rej_repo.count()

        proc_repo = ProcessedDataRepository(session)
        total_valid = proc_repo.count()

        total = total_valid + total_rejected
        pass_rate = round((total_valid / total) * 100.0, 2) if total > 0 else 100.0

        return success_response({
            "total_valid_records": total_valid,
            "total_rejected_records": total_rejected,
            "pass_rate_percentage": pass_rate,
            "reasons_breakdown": rejection_summary,
            "recent_rejections": [r.to_dict() for r in recent_rejections],
        })
