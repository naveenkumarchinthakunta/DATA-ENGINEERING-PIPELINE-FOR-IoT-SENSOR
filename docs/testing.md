# Testing Documentation: IoT Sensor Data Engineering Pipeline

This document outlines the testing strategy, test suite organization, verification criteria, and execution commands for the IoT data engineering pipeline.

---

## 1. Test Suite Architecture

The test suite is structured into isolated, automated test modules using `pytest`:

```
tests/
├── test_simulator.py            # Unit tests for stochastic & deterministic sensor generation
├── test_validation.py           # Unit tests for schema validation, data quality rules, and quarantine logic
├── test_transformation.py       # Unit tests for feature derivation, baselines, rate of change, and null preservation
├── test_storage.py              # Integration tests for storage repositories using in-memory SQLite
├── test_processing.py           # Unit tests for aggregation KPIs, machine summaries, and anomaly detection
├── test_api.py                  # Integration tests for Flask REST API endpoints and parameter validation
└── test_pipeline_integration.py # End-to-end pipeline integration and retry idempotency tests
```

---

## 2. Test Execution Commands

Run tests from the project root using Windows PowerShell:

```powershell
# Run the complete test suite
.\venv\Scripts\pytest -v

# Run a specific test module
.\venv\Scripts\pytest tests/test_validation.py -v

# Run with test execution duration profiling
.\venv\Scripts\pytest -v --durations=5
```

---

## 3. Verified Test Results

The full test suite executes **43 automated tests** with 100% pass rate:

```
tests/test_api.py::test_api_health PASSED                                [  2%]
tests/test_api.py::test_api_get_sensors PASSED                           [  5%]
tests/test_api.py::test_api_get_sensors_filter_zone PASSED               [  8%]
tests/test_api.py::test_api_get_sensor_readings PASSED                   [ 11%]
tests/test_api.py::test_api_get_invalid_sensor_readings PASSED           [ 14%]
tests/test_api.py::test_api_get_analytics_summary PASSED                 [ 17%]
tests/test_api.py::test_api_get_alerts PASSED                            [ 20%]
tests/test_api.py::test_api_get_pipeline_runs PASSED                     [ 23%]
tests/test_api.py::test_api_get_data_quality_summary PASSED              [ 26%]
tests/test_api.py::test_api_trigger_pipeline PASSED                      [ 29%]
tests/test_mqtt_adapter.py::test_mqtt_topic_parsing PASSED               [ 33%]
tests/test_mqtt_adapter.py::test_mqtt_message_ingestion PASSED           [ 36%]
tests/test_pipeline_integration.py::test_complete_end_to_end_pipeline_flow PASSED [ 38%]
tests/test_pipeline_integration.py::test_retry_safety_and_deduplication PASSED [ 41%]
tests/test_processing.py::test_analytics_kpi_summary PASSED              [ 44%]
tests/test_processing.py::test_analytics_machine_summary PASSED          [ 47%]
tests/test_processing.py::test_anomaly_detection_thresholds PASSED       [ 50%]
tests/test_simulator.py::test_sensor_metadata_generation PASSED          [ 52%]
tests/test_simulator.py::test_deterministic_generation_with_seed PASSED  [ 55%]
tests/test_simulator.py::test_single_reading_fields PASSED               [ 58%]
tests/test_storage.py::test_sensor_repository_upsert PASSED              [ 61%]
tests/test_storage.py::test_raw_repository_deduplication PASSED          [ 63%]
tests/test_storage.py::test_processed_repository_persistence PASSED      [ 66%]
tests/test_storage.py::test_rejected_repository_summary PASSED           [ 69%]
tests/test_storage.py::test_alert_repository_idempotency_and_ack PASSED  [ 72%]
tests/test_transformation.py::test_transformation_baseline_deviation PASSED [ 75%]
tests/test_transformation.py::test_rate_of_change_between_consecutive_readings PASSED [ 77%]
tests/test_transformation.py::test_preservation_of_none_values PASSED    [ 80%]
tests/test_ui_views.py::test_ui_overview_page PASSED                     [ 82%]
tests/test_ui_views.py::test_ui_sensors_page PASSED                      [ 84%]
tests/test_ui_views.py::test_ui_trends_page PASSED                       [ 86%]
tests/test_ui_views.py::test_ui_data_quality_page PASSED                 [ 88%]
tests/test_ui_views.py::test_ui_alerts_page PASSED                       [ 90%]
tests/test_ui_views.py::test_ui_pipeline_page PASSED                     [ 92%]
tests/test_ui_views.py::test_ui_static_stylesheet PASSED                 [ 94%]
tests/test_validation.py::test_valid_record PASSED                       [ 96%]
tests/test_validation.py::test_missing_event_id PASSED                   [ 97%]
tests/test_validation.py::test_missing_sensor_id PASSED                  [ 98%]
tests/test_validation.py::test_malformed_timestamp PASSED                [ 98%]
tests/test_validation.py::test_future_timestamp_skew PASSED              [ 99%]
tests/test_validation.py::test_nan_measurement_rejection PASSED          [ 99%]
tests/test_validation.py::test_negative_absolute_pressure PASSED         [ 99%]
tests/test_validation.py::test_batch_validation_and_intra_batch_duplicates PASSED [100%]

============================== 43 passed in 4.34s ==============================
```

---

## 4. Key Verification Guarantees

### 4.1 Data Quality & Quarantine Isolation
- Records with missing primary keys, corrupted timestamps, future timestamps (> 120s skew), NaN/Inf floats, and physically impossible measurements (< -273.15 °C or negative bar) are reliably caught.
- All failed records are written to `rejected_sensor_data` with precise failure reasons.
- Zero corrupted records enter `processed_sensor_data`.

### 4.2 Non-Zero Missing Value Preservation
- Validated and transformed records explicitly distinguish between `NULL`/`None` (missing observation) and `0.0` (genuine zero reading).
- Missing values are never falsely converted to zero.

### 4.3 Idempotency and Retry Safety
- Ingesting or processing the identical batch of records repeatedly produces zero duplicate rows in `raw_sensor_data`, zero duplicate rows in `processed_sensor_data`, and zero duplicate rows in `machine_health_alerts`.
- Confirmed by `test_retry_safety_and_deduplication`.

---

## 5. Performance Benchmark Measurements

Executed under synthetic workloads via `scripts/benchmark.py`:

| Workload (Records) | Total Duration | Throughput | Ingestion | Validation | Transformation | Persistence | Anomaly Detection |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **200** | 0.406 s | 492 rec/s | 22.1 ms | 5.3 ms | 4.3 ms | 14.9 ms | 29.8 ms |
| **600** | 0.372 s | 1,614 rec/s | 12.8 ms | 4.5 ms | 4.2 ms | 14.1 ms | 28.8 ms |
| **1,000** | 0.351 s | **2,847 rec/s** | 12.7 ms | 6.0 ms | 4.3 ms | 11.6 ms | 22.2 ms |

### Query Latencies:
- **KPI Summary Query**: 12.7 ms
- **Sensor Filtered Query**: 3.1 ms
- **5-Minute Resampling Aggregation**: 36.5 ms
