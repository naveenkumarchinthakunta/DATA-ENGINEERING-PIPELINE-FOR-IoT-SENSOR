"""
Unified Command-Line Interface (CLI) Management Tool.
Provides operators and data engineers with commands for database initialization,
streaming simulation, health inspection, alert management, and dataset exports.

Usage examples:
  python scripts/cli.py status
  python scripts/cli.py ingest --batch-size 200
  python scripts/cli.py stream --interval 3 --cycles 5
  python scripts/cli.py alerts --active-only
  python scripts/cli.py quarantine --limit 10
  python scripts/cli.py export --table processed --format csv --output data/processed_export.csv
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.database import init_db, get_db_session, check_db_health
from storage.repositories import (
    SensorRepository,
    RawDataRepository,
    ProcessedDataRepository,
    RejectedDataRepository,
    AlertRepository,
    PipelineRunRepository,
)
from pipeline.pipeline_runner import PipelineRunner
from processing.aggregation import AnalyticsEngine
from monitoring.logging_config import logger


def cmd_status(args):
    """Displays current system metrics and table statistics."""
    with get_db_session() as session:
        analytics = AnalyticsEngine(session)
        summary = analytics.get_overall_summary()

        print("\n" + "=" * 60)
        print("          IOT PIPELINE - OPERATIONAL STATUS")
        print("=" * 60)
        print(f" Database Health      : {'CONNECTED' if check_db_health() else 'DISCONNECTED'}")
        print(f" Registered Sensors   : {summary['total_registered_sensors']}")
        print(f" Active (Reporting)   : {summary['active_sensors']}")
        print(f" Inactive Sensors     : {summary['inactive_sensors']}")
        print("-" * 60)
        print(f" Total Raw Records    : {summary['total_raw_records']}")
        print(f" Processed Records    : {summary['total_processed_records']}")
        print(f" Quarantined Records  : {summary['total_rejected_records']}")
        print(f" Quality Pass Rate    : {summary['validation_success_rate']}%")
        print(f" Defect Rate          : {summary['data_rejection_rate']}%")
        print("-" * 60)
        print(f" Total Alerts         : {summary['total_alerts']} ({summary['active_alerts']} active)")
        print(f" Pipeline Cycles Run  : {summary['pipeline_runs_count']} ({summary['pipeline_success_rate']}% success)")
        print(f" Last Successful Run  : {summary['last_successful_run'] or 'None'}")
        print("=" * 60 + "\n")


def cmd_ingest(args):
    """Executes a single pipeline ingestion & transformation cycle."""
    runner = PipelineRunner()
    print(f"Starting pipeline cycle with batch_size={args.batch_size}...")
    t0 = time.perf_counter()
    summary = runner.run_cycle(batch_size=args.batch_size)
    duration = time.perf_counter() - t0

    print(f"\n[DONE] Pipeline run {summary.run_id} completed in {duration:.3f}s:")
    print(f"  - Received     : {summary.records_received}")
    print(f"  - Ingested Raw : {summary.records_ingested}")
    print(f"  - Processed    : {summary.records_processed}")
    print(f"  - Quarantined  : {summary.records_rejected}")
    print(f"  - Alerts Raised: {summary.alerts_generated}\n")


def cmd_stream(args):
    """Continuously runs pipeline simulation cycles."""
    runner = PipelineRunner()
    print(f"Starting continuous stream: interval={args.interval}s, max_cycles={args.cycles or 'infinite'}")
    cycle = 0
    try:
        while True:
            cycle += 1
            summary = runner.run_cycle(batch_size=args.batch_size)
            print(f"[Cycle {cycle:>3}] Status: {summary.status} | Proc: {summary.records_processed} | Rej: {summary.records_rejected} | Alerts: {summary.alerts_generated}")
            if args.cycles and cycle >= args.cycles:
                print("Completed requested number of cycles.")
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStreaming halted by user.")


def cmd_alerts(args):
    """Lists operational health alerts."""
    with get_db_session() as session:
        repo = AlertRepository(session)
        status_filter = "ACTIVE" if args.active_only else None
        alerts, total = repo.get_alerts(status=status_filter, per_page=args.limit)

        print(f"\nShowing {len(alerts)} of {total} alerts (Filter: status={status_filter or 'ALL'}):")
        print("-" * 80)
        print(f"{'ALERT ID':<16} {'SEVERITY':<10} {'TYPE':<18} {'MACHINE':<9} {'SENSOR':<8} {'VALUE':<8} {'THRESH':<8}")
        print("-" * 80)
        for a in alerts:
            val_str = f"{a.measured_value:.2f}" if a.measured_value is not None else "N/A"
            th_str = f"{a.configured_threshold:.2f}" if a.configured_threshold is not None else "N/A"
            print(f"{a.alert_id:<16} {a.severity:<10} {a.alert_type:<18} {a.machine_id:<9} {a.sensor_id:<8} {val_str:<8} {th_str:<8}")
        print("-" * 80 + "\n")


def cmd_quarantine(args):
    """Inspects recent quarantined defect records."""
    with get_db_session() as session:
        repo = RejectedDataRepository(session)
        rejections = repo.get_recent_rejections(limit=args.limit)

        print(f"\nShowing {len(rejections)} latest quarantined records:")
        print("-" * 80)
        print(f"{'ID':<6} {'SENSOR':<8} {'TIMESTAMP':<22} {'REASON'}")
        print("-" * 80)
        for r in rejections:
            ts_str = r.rejection_timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.rejection_timestamp else "N/A"
            print(f"{r.rejection_id:<6} {r.sensor_id or 'N/A':<8} {ts_str:<22} {r.rejection_reason[:40]}")
        print("-" * 80 + "\n")


def cmd_export(args):
    """Exports data table to CSV or JSON format for downstream analytical workloads."""
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with get_db_session() as session:
        if args.table == "processed":
            repo = ProcessedDataRepository(session)
            records = [r.to_dict() for r in repo.get_recent_readings(limit=args.limit)]
        elif args.table == "sensors":
            repo = SensorRepository(session)
            records = [s.to_dict() for s in repo.get_all()]
        elif args.table == "alerts":
            repo = AlertRepository(session)
            alerts, _ = repo.get_alerts(per_page=args.limit)
            records = [a.to_dict() for a in alerts]
        elif args.table == "rejected":
            repo = RejectedDataRepository(session)
            records = [r.to_dict() for r in repo.get_recent_rejections(limit=args.limit)]
        else:
            print(f"Unknown table '{args.table}'. Options: processed, sensors, alerts, rejected")
            return

    if not records:
        print("No records found to export.")
        return

    if args.format == "csv":
        keys = records[0].keys()
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(records)
        print(f"Exported {len(records)} records to CSV: {out_path}")
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)
        print(f"Exported {len(records)} records to JSON: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Industrial IoT Data Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Display operational KPIs and table row counts")
    p_status.set_defaults(func=cmd_status)

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Run a single pipeline batch cycle")
    p_ingest.add_argument("--batch-size", type=int, default=200, help="Batch size")
    p_ingest.set_defaults(func=cmd_ingest)

    # stream
    p_stream = subparsers.add_parser("stream", help="Run continuous streaming pipeline")
    p_stream.add_argument("--interval", type=int, default=3, help="Interval seconds")
    p_stream.add_argument("--cycles", type=int, default=0, help="Cycles (0 = infinite)")
    p_stream.add_argument("--batch-size", type=int, default=200, help="Batch size")
    p_stream.set_defaults(func=cmd_stream)

    # alerts
    p_alerts = subparsers.add_parser("alerts", help="List operational alarms")
    p_alerts.add_argument("--active-only", action="store_true", help="Filter active only")
    p_alerts.add_argument("--limit", type=int, default=20, help="Max rows")
    p_alerts.set_defaults(func=cmd_alerts)

    # quarantine
    p_quar = subparsers.add_parser("quarantine", help="Inspect quarantined defect records")
    p_quar.add_argument("--limit", type=int, default=20, help="Max rows")
    p_quar.set_defaults(func=cmd_quarantine)

    # export
    p_exp = subparsers.add_parser("export", help="Export dataset to CSV or JSON")
    p_exp.add_argument("--table", choices=["processed", "sensors", "alerts", "rejected"], default="processed")
    p_exp.add_argument("--format", choices=["csv", "json"], default="csv")
    p_exp.add_argument("--limit", type=int, default=5000, help="Max records to export")
    p_exp.add_argument("--output", default="data/export.csv", help="Output file path")
    p_exp.set_defaults(func=cmd_export)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
