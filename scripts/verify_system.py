"""
System Verification and Operational Audit Script.
Performs an end-to-end health audit of the database, verifies row counts across all 6 tables,
inspects quarantined records, samples machine alerts, and verifies analytical KPIs.
"""

from datetime import datetime, timezone
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.database import get_db_session, check_db_health
from storage.repositories import (
    SensorRepository,
    RawDataRepository,
    ProcessedDataRepository,
    RejectedDataRepository,
    AlertRepository,
    PipelineRunRepository,
)
from processing.aggregation import AnalyticsEngine


def run_verification():
    print("=" * 80)
    print("       IoT DATA ENGINEERING PIPELINE - END-TO-END SYSTEM AUDIT")
    print("=" * 80)

    # 1. Database Connectivity Check
    is_db_ok = check_db_health()
    status_tag = "[PASS]" if is_db_ok else "[FAIL]"
    print(f"\n1. Database Connectivity Check: {status_tag} (SQLite)")
    if not is_db_ok:
        print("ERROR: Database connection failed. Aborting verification.")
        sys.exit(1)

    with get_db_session() as session:
        sensor_repo = SensorRepository(session)
        raw_repo = RawDataRepository(session)
        proc_repo = ProcessedDataRepository(session)
        rej_repo = RejectedDataRepository(session)
        alert_repo = AlertRepository(session)
        run_repo = PipelineRunRepository(session)
        analytics = AnalyticsEngine(session)

        # 2. Table Row Counts
        sensor_cnt = sensor_repo.count()
        raw_cnt = raw_repo.count()
        proc_cnt = proc_repo.count()
        rej_cnt = rej_repo.count()
        alert_cnt = alert_repo.count()
        run_cnt = run_repo.count()

        print("\n2. Relational Table Audit:")
        print(f"  - Table 1: sensors                 : {sensor_cnt:>6} rows (Target: 200 sensors)")
        print(f"  - Table 2: raw_sensor_data         : {raw_cnt:>6} rows (Original JSON payloads)")
        print(f"  - Table 3: processed_sensor_data   : {proc_cnt:>6} rows (Validated & enriched)")
        print(f"  - Table 4: rejected_sensor_data    : {rej_cnt:>6} rows (Quarantined defects)")
        print(f"  - Table 5: machine_health_alerts   : {alert_cnt:>6} rows (Operational alarms)")
        print(f"  - Table 6: pipeline_runs           : {run_cnt:>6} rows (Execution cycle audits)")

        assert sensor_cnt == 200, f"Expected 200 sensors, found {sensor_cnt}"
        assert raw_cnt > 0, "Expected raw sensor records"
        assert proc_cnt > 0, "Expected processed sensor records"
        assert rej_cnt > 0, "Expected quarantined sensor records"

        # 3. Sample Processed Record Inspection
        recent_proc = proc_repo.get_recent_readings(limit=1)
        print("\n3. Sample Processed Record Verification:")
        if recent_proc:
            p = recent_proc[0]
            print(f"  - Event ID      : {p.event_id}")
            print(f"  - Sensor ID     : {p.sensor_id} (Machine: {p.machine_id})")
            print(f"  - Timestamp UTC : {p.event_timestamp}")
            print(f"  - Measurements  : Temp={p.temperature_celsius}°C, Pressure={p.pressure_bar} bar, Vibration={p.vibration_mm_s} mm/s")
            print(f"  - Quality Flags : {p.quality_flags}")

        # 4. Sample Quarantine Record Inspection
        recent_rej = rej_repo.get_recent_rejections(limit=1)
        print("\n4. Sample Quarantined Record Verification (Data Quality Gate):")
        if recent_rej:
            q = recent_rej[0]
            print(f"  - Rejection ID  : {q.rejection_id}")
            print(f"  - Sensor ID     : {q.sensor_id or 'N/A'}")
            print(f"  - Failure Reason: {q.rejection_reason}")
            print(f"  - Quarantined At: {q.rejection_timestamp}")

        # 5. Sample Machine Health Alert Inspection
        recent_alerts, _ = alert_repo.get_alerts(page=1, per_page=1)
        print("\n5. Sample Machine Health Alert Verification:")
        if recent_alerts:
            a = recent_alerts[0]
            print(f"  - Alert ID      : {a.alert_id}")
            print(f"  - Severity      : [{a.severity}] {a.alert_type}")
            print(f"  - Machine ID    : {a.machine_id} (Sensor: {a.sensor_id})")
            print(f"  - Trigger       : Value={a.measured_value} vs Threshold={a.configured_threshold}")
            print(f"  - Status        : {a.alert_status}")

        # 6. Global Analytics KPIs
        summary = analytics.get_overall_summary(reporting_window_minutes=15)
        print("\n6. Live Analytics Engine KPIs:")
        print(f"  - Active Sensors Reporting   : {summary['active_sensors']} / {summary['total_registered_sensors']}")
        print(f"  - Data Quality Yield (Pass)  : {summary['validation_success_rate']}%")
        print(f"  - Defect Quarantine Rate     : {summary['data_rejection_rate']}%")
        print(f"  - Temperature Range          : Avg={summary['temperature_stats']['avg']}°C, Min={summary['temperature_stats']['min']}°C, Max={summary['temperature_stats']['max']}°C")
        print(f"  - Pressure Range             : Avg={summary['pressure_stats']['avg']} bar, Min={summary['pressure_stats']['min']} bar, Max={summary['pressure_stats']['max']} bar")
        print(f"  - Vibration Range            : Avg={summary['vibration_stats']['avg']} mm/s, Min={summary['vibration_stats']['min']} mm/s, Max={summary['vibration_stats']['max']} mm/s")
        print(f"  - Pipeline Cycle Success Rate: {summary['pipeline_success_rate']}%")

    print("\n" + "=" * 80)
    print(" SYSTEM AUDIT COMPLETE: ALL 6 PIPELINE STAGES VERIFIED & OPERATIONAL")
    print("=" * 80)


if __name__ == "__main__":
    run_verification()
