"""
Industrial Telemetry Exploratory Data Analysis & Machine Health Scoring.
Loads processed records directly from the relational database, computes distribution statistics,
cross-sensor correlations, and calculates composite Machine Health Scores (0 - 100).
"""

from datetime import datetime, timezone
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.database import get_db_session
from storage.repositories import ProcessedDataRepository, AlertRepository, SensorRepository


def run_exploratory_analysis():
    print("=" * 80)
    print("  EXPLORATORY DATA ANALYSIS & MACHINE HEALTH SCORING INDEX")
    print("=" * 80)

    with get_db_session() as session:
        proc_repo = ProcessedDataRepository(session)
        alert_repo = AlertRepository(session)
        sensor_repo = SensorRepository(session)

        # 1. Fetch Processed Telemetry
        readings = proc_repo.get_recent_readings(limit=5000)
        alerts, _ = alert_repo.get_alerts(per_page=2000)
        sensors = sensor_repo.get_all()

        print(f"\nLoaded {len(readings)} telemetry readings across {len(sensors)} registered sensors.")

        if not readings:
            print("No telemetry records found. Run an ingestion cycle first.")
            return

        data = [
            {
                "sensor_id": r.sensor_id,
                "machine_id": r.machine_id,
                "temperature": r.temperature_celsius,
                "pressure": r.pressure_bar,
                "vibration": r.vibration_mm_s,
            }
            for r in readings
            if r.temperature_celsius is not None
        ]
        df = pd.DataFrame(data)

        # 2. Distribution Statistics (Quantiles & Skew)
        print("\n1. Telemetry Distribution & Quantiles:")
        print("-" * 80)
        for col in ["temperature", "pressure", "vibration"]:
            p25 = df[col].quantile(0.25)
            p50 = df[col].quantile(0.50)
            p75 = df[col].quantile(0.75)
            iqr = p75 - p25
            print(f"  - {col.capitalize():<12}: Median={p50:6.2f} | 25%={p25:6.2f} | 75%={p75:6.2f} | IQR={iqr:6.2f}")

        # 3. Correlation Matrix
        corr = df[["temperature", "pressure", "vibration"]].corr()
        print("\n2. Telemetry Cross-Measurement Pearson Correlation:")
        print("-" * 80)
        print(corr.round(3).to_string())

        # 4. Machine Health Scoring Model (0 - 100)
        # Higher score = Healthier machine. Penalty for alerts and abnormal variations.
        alert_counts = {}
        for a in alerts:
            alert_counts[a.machine_id] = alert_counts.get(a.machine_id, 0) + (
                3 if a.severity == "CRITICAL" else 1
            )

        machine_groups = df.groupby("machine_id")
        machine_stats = []

        for m_id, grp in machine_groups:
            penalty = alert_counts.get(m_id, 0) * 1.5
            temp_var = grp["temperature"].std() if len(grp) > 1 else 0
            vib_mean = grp["vibration"].mean()

            # Base score 100 with deduction for alerts and high vibration
            health_score = max(10.0, round(100.0 - penalty - (vib_mean * 3.0), 1))
            status = "OPTIMAL" if health_score >= 85 else ("NEEDS_INSPECTION" if health_score >= 65 else "AT_RISK")

            machine_stats.append({
                "machine_id": m_id,
                "readings": len(grp),
                "avg_temp": round(grp["temperature"].mean(), 1),
                "avg_press": round(grp["pressure"].mean(), 2),
                "avg_vib": round(vib_mean, 2),
                "weighted_alerts": alert_counts.get(m_id, 0),
                "health_score": health_score,
                "status": status,
            })

        m_df = pd.DataFrame(machine_stats).sort_values(by="health_score", ascending=True)

        print("\n3. Machine Fleet Health Index Ranking (Lowest to Highest Health):")
        print("-" * 80)
        print(f"{'MACHINE':<9} {'READINGS':<9} {'AVG TEMP':<10} {'AVG PRESS':<11} {'AVG VIB':<9} {'ALERTS':<8} {'SCORE':<7} {'STATUS'}")
        print("-" * 80)
        for _, row in m_df.iterrows():
            print(f"{row['machine_id']:<9} {row['readings']:<9} {row['avg_temp']:<10.1f} {row['avg_press']:<11.2f} {row['avg_vib']:<9.2f} {row['weighted_alerts']:<8} {row['health_score']:<7.1f} {row['status']}")
        print("-" * 80)

    print("\n" + "=" * 80)
    print(" Exploratory analysis completed.")
    print("=" * 80)


if __name__ == "__main__":
    run_exploratory_analysis()
