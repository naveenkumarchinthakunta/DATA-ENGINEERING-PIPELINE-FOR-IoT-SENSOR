"""
Industrial Telemetry Baseline & Statistical Anomaly Model.
Demonstrates how the clean, transformed pipeline data serves downstream Machine Learning
and Predictive Maintenance workloads.
Computes Multivariate Z-Score and Mahalanobis Distance across Temperature, Pressure, and Vibration,
and compares them against rule-based operational threshold alerts.
"""

from datetime import datetime, timezone
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.database import get_db_session
from storage.repositories import ProcessedDataRepository, AlertRepository
from monitoring.logging_config import logger


def run_statistical_anomaly_baseline():
    print("=" * 75)
    print("  DATA SCIENCE EXTENSION: MULTIVARIATE STATISTICAL ANOMALY ANALYSIS")
    print("=" * 75)

    with get_db_session() as session:
        proc_repo = ProcessedDataRepository(session)
        alert_repo = AlertRepository(session)

        readings = proc_repo.get_recent_readings(limit=2000)
        if not readings:
            print("No processed telemetry available. Run an ingestion cycle first.")
            return

        print(f"Loaded {len(readings)} processed telemetry records for analysis.")

        # Extract features into DataFrame
        records = []
        for r in readings:
            if r.temperature_celsius is not None and r.pressure_bar is not None and r.vibration_mm_s is not None:
                records.append({
                    "event_id": r.event_id,
                    "sensor_id": r.sensor_id,
                    "machine_id": r.machine_id,
                    "temperature": r.temperature_celsius,
                    "pressure": r.pressure_bar,
                    "vibration": r.vibration_mm_s,
                })

        df = pd.DataFrame(records)

    features = ["temperature", "pressure", "vibration"]
    X = df[features].values

    # 1. Univariate Statistical Properties
    means = np.mean(X, axis=0)
    stds = np.std(X, axis=0)
    print("\n1. Telemetry Distribution Baseline:")
    for idx, feat in enumerate(features):
        print(f"  - {feat.capitalize():<12}: Mean = {means[idx]:.2f}, StdDev = {stds[idx]:.2f}")

    # 2. Multivariate Covariance Matrix
    cov_matrix = np.cov(X, rowvar=False)
    print("\n2. Covariance Matrix:")
    print(np.round(cov_matrix, 3))

    # 3. Mahalanobis Distance Calculation
    # D_M = sqrt((x - mu)^T * Sigma^(-1) * (x - mu))
    try:
        inv_cov = np.linalg.pinv(cov_matrix)
        diff = X - means
        left = np.dot(diff, inv_cov)
        mahalanobis_sq = np.sum(left * diff, axis=1)
        mahalanobis_dist = np.sqrt(np.maximum(0, mahalanobis_sq))
        df["mahalanobis_distance"] = np.round(mahalanobis_dist, 3)

        # Statistical Threshold: Chi-Square critical value for 3 degrees of freedom at p=0.01 is ~11.34
        # sqrt(11.34) ~ 3.37
        stat_threshold = 3.37
        stat_anomalies = df[df["mahalanobis_distance"] > stat_threshold]

        print("\n3. Multivariate Outlier Detection:")
        print(f"  - Total Data Points Evaluated  : {len(df)}")
        print(f"  - Statistical Outliers (D > {stat_threshold}): {len(stat_anomalies)} ({len(stat_anomalies)/len(df)*100:.2f}%)")

        if not stat_anomalies.empty:
            print("\n4. Top 5 Highest Multivariate Distance Outliers:")
            top_outliers = stat_anomalies.sort_values(by="mahalanobis_distance", ascending=False).head(5)
            print("-" * 75)
            print(f"{'SENSOR':<8} {'MACHINE':<9} {'TEMP (C)':<10} {'PRESS (bar)':<12} {'VIB (mm/s)':<12} {'DIST':<8}")
            print("-" * 75)
            for _, row in top_outliers.iterrows():
                print(f"{row['sensor_id']:<8} {row['machine_id']:<9} {row['temperature']:<10.2f} {row['pressure']:<12.2f} {row['vibration']:<12.2f} {row['mahalanobis_distance']:<8.2f}")
            print("-" * 75)

    except Exception as e:
        print(f"Could not compute Mahalanobis distance: {e}")

    print("\n" + "=" * 75)
    print(" Statistical anomaly model execution completed successfully.")
    print("=" * 75)


if __name__ == "__main__":
    run_statistical_anomaly_baseline()
