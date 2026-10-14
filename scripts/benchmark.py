"""
Performance and Scalability Benchmark Script.
Measures ingestion throughput, stage-by-stage latencies, and analytical query latency
under documented synthetic workloads (e.g. 500 and 1,000 records).
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.database import init_db, get_db_session
from pipeline.pipeline_runner import PipelineRunner
from processing.aggregation import AnalyticsEngine
from storage.repositories import ProcessedDataRepository
from simulator.sensor_simulator import SensorSimulator
from monitoring.logging_config import logger


def run_benchmark():
    init_db()
    print("=" * 70)
    print(" IoT DATA ENGINEERING PIPELINE - PERFORMANCE BENCHMARK")
    print("=" * 70)

    workload_sizes = [200, 600, 1000]

    for size in workload_sizes:
        print(f"\n--- Testing Workload: {size} sensor events ---")
        simulator = SensorSimulator(total_sensors=200)
        runner = PipelineRunner(simulator=simulator)

        # 1. Pipeline End-to-End Execution
        t0 = time.perf_counter()
        summary = runner.run_cycle(batch_size=size)
        total_time = time.perf_counter() - t0

        throughput = round(size / total_time, 2)
        print(f"Total Pipeline Duration: {total_time:.3f} s")
        print(f"Overall Throughput:      {throughput} records/second")
        print(f"Stage Breakdown (ms):")
        for stage, ms in summary.stage_timings.items():
            print(f"  - {stage:<22}: {ms:.2f} ms")

        # 2. Query Latency Benchmark
        with get_db_session() as session:
            analytics = AnalyticsEngine(session)
            proc_repo = ProcessedDataRepository(session)

            # Measure overall summary query latency
            q0 = time.perf_counter()
            analytics.get_overall_summary()
            q_summary_ms = (time.perf_counter() - q0) * 1000

            # Measure sensor filtered query latency
            q1 = time.perf_counter()
            proc_repo.get_readings_by_sensor("S001", page=1, per_page=50)
            q_sensor_ms = (time.perf_counter() - q1) * 1000

            # Measure time window aggregation latency
            q2 = time.perf_counter()
            analytics.get_time_window_aggregations(window="5min")
            q_window_ms = (time.perf_counter() - q2) * 1000

        print(f"Query Latency:")
        print(f"  - KPI Summary Query    : {q_summary_ms:.2f} ms")
        print(f"  - Sensor Lookup Query  : {q_sensor_ms:.2f} ms")
        print(f"  - Time-Window Agg Query: {q_window_ms:.2f} ms")

    print("\n" + "=" * 70)
    print(" Benchmark completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
