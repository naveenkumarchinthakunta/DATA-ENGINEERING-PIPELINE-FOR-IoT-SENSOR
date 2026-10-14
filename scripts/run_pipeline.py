"""
Pipeline Execution Runner Script.
Supports single-cycle execution or continuous real-time execution loops.
Usage:
  python scripts/run_pipeline.py
  python scripts/run_pipeline.py --continuous --interval 5 --cycles 10
"""

import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.pipeline_runner import PipelineRunner
from storage.database import init_db
from monitoring.logging_config import logger


def main():
    parser = argparse.ArgumentParser(description="IoT Data Engineering Pipeline Runner")
    parser.add_argument("--batch-size", type=int, default=200, help="Number of sensor events per cycle")
    parser.add_argument("--continuous", action="store_true", help="Run continuously in a loop")
    parser.add_argument("--interval", type=int, default=5, help="Interval between runs in seconds (continuous mode)")
    parser.add_argument("--cycles", type=int, default=0, help="Max cycles to run (0 = infinite in continuous mode)")
    args = parser.parse_args()

    init_db()
    runner = PipelineRunner()

    if not args.continuous:
        logger.info("Running single pipeline cycle with batch_size=%d", args.batch_size)
        summary = runner.run_cycle(batch_size=args.batch_size)
        print(f"Cycle finished: {summary.status} in {summary.duration_seconds}s. Processed: {summary.records_processed}, Quarantined: {summary.records_rejected}, Alerts: {summary.alerts_generated}")
    else:
        logger.info("Starting continuous pipeline execution (interval=%ds, max_cycles=%d)...", args.interval, args.cycles)
        cycle_count = 0
        try:
            while True:
                cycle_count += 1
                logger.info("--- Executing Cycle #%d ---", cycle_count)
                summary = runner.run_cycle(batch_size=args.batch_size)
                print(f"[Cycle {cycle_count}] Status: {summary.status} | Processed: {summary.records_processed} | Quarantined: {summary.records_rejected} | Alerts: {summary.alerts_generated}")

                if args.cycles > 0 and cycle_count >= args.cycles:
                    logger.info("Reached maximum cycles limit (%d). Exiting.", args.cycles)
                    break

                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Pipeline runner halted by user (SIGINT).")
            print("\nPipeline execution halted safely.")


if __name__ == "__main__":
    main()
