# Data Dictionary: IoT Sensor Data Engineering Pipeline

This document defines the relational database schema, data types, constraints, and operational interpretations for all tables in the pipeline.

---

## 1. Table: `sensors`
Stores metadata and operating threshold limits for registered factory IoT sensors.

| Column Name | Data Type | Nullable | Key / Constraint | Description | Example Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `sensor_id` | VARCHAR(50) | No | PRIMARY KEY | Unique sensor identifier | `"S001"` |
| `machine_id` | VARCHAR(50) | No | INDEX | Identifier of the machine to which sensor is attached | `"M01"` |
| `factory_zone` | VARCHAR(50) | No | INDEX | Physical factory sector | `"Zone-North"` |
| `sensor_status` | VARCHAR(20) | No | DEFAULT 'ACTIVE' | Operational status (`ACTIVE`, `INACTIVE`, `MAINTENANCE`) | `"ACTIVE"` |
| `temperature_limit_min` | FLOAT | No | DEFAULT 20.0 | Minimum normal operating temperature (°C) | `20.0` |
| `temperature_limit_max` | FLOAT | No | DEFAULT 85.0 | Maximum normal operating temperature (°C) | `85.0` |
| `pressure_limit_min` | FLOAT | No | DEFAULT 1.0 | Minimum normal operating pressure (bar) | `1.0` |
| `pressure_limit_max` | FLOAT | No | DEFAULT 10.0 | Maximum normal operating pressure (bar) | `10.0` |
| `vibration_limit_min` | FLOAT | No | DEFAULT 0.0 | Minimum normal vibration amplitude (mm/s) | `0.0` |
| `vibration_limit_max` | FLOAT | No | DEFAULT 5.0 | Maximum normal vibration amplitude (mm/s) | `5.0` |
| `created_at` | DATETIME | No | DEFAULT UTC | Record creation timestamp | `2026-10-13 10:00:00` |
| `updated_at` | DATETIME | No | DEFAULT UTC | Record update timestamp | `2026-10-13 10:00:00` |

---

## 2. Table: `raw_sensor_data`
Stores raw sensor payloads immediately upon ingestion to preserve lineage and replayability.

| Column Name | Data Type | Nullable | Key / Constraint | Description | Example Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `event_id` | VARCHAR(100) | No | PRIMARY KEY | Unique event identifier from sensor telemetry | `"evt_a9b1c2d3"` |
| `sensor_id` | VARCHAR(50) | No | INDEX | Source sensor identifier | `"S001"` |
| `event_timestamp` | DATETIME | No | INDEX | Timestamp recorded at event generation (UTC) | `2026-10-13 10:15:30` |
| `ingestion_timestamp` | DATETIME | No | INDEX | Timestamp recorded when payload was received | `2026-10-13 10:15:32` |
| `raw_payload` | TEXT | No | | Full unaltered JSON string of original payload | `{"event_id": "...", ...}` |
| `ingestion_status` | VARCHAR(30) | No | DEFAULT 'RECEIVED' | Status (`RECEIVED`, `DUPLICATE`, `FAILED`) | `"RECEIVED"` |

**Composite Index**: `idx_raw_sensor_time (sensor_id, event_timestamp)`

---

## 3. Table: `processed_sensor_data`
Stores validated, standardized, and feature-enriched telemetry records ready for querying.

| Column Name | Data Type | Nullable | Key / Constraint | Description | Example Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `event_id` | VARCHAR(100) | No | PRIMARY KEY | Source event identifier | `"evt_a9b1c2d3"` |
| `sensor_id` | VARCHAR(50) | No | INDEX | Standardized sensor identifier | `"S001"` |
| `machine_id` | VARCHAR(50) | No | INDEX | Standardized machine identifier | `"M01"` |
| `event_timestamp` | DATETIME | No | INDEX | Normalized event timestamp (UTC) | `2026-10-13 10:15:30` |
| `temperature_celsius` | FLOAT | Yes | | Measured temperature in Celsius (NULL if missing) | `52.4` |
| `pressure_bar` | FLOAT | Yes | | Measured pressure in bar (NULL if missing) | `4.2` |
| `vibration_mm_s` | FLOAT | Yes | | Measured vibration amplitude in mm/s | `1.35` |
| `validation_status` | VARCHAR(20) | No | DEFAULT 'VALID' | Conformance verification status | `"VALID"` |
| `transformation_timestamp` | DATETIME | No | DEFAULT UTC | Time when transformation executed | `2026-10-13 10:15:33` |
| `quality_flags` | TEXT | Yes | | JSON string of derived operational features | *(See schema below)* |

**Composite Indexes**:
- `idx_processed_sensor_time (sensor_id, event_timestamp)`
- `idx_processed_machine_time (machine_id, event_timestamp)`

### Structure of `quality_flags` JSON Field:
```json
{
  "temp_deviation": 2.4,
  "press_deviation": -0.3,
  "vib_deviation": -0.15,
  "seconds_since_last_event": 5.0,
  "temp_rate_of_change_per_sec": 0.48,
  "press_rate_of_change_per_sec": -0.06,
  "vib_rate_of_change_per_sec": 0.02,
  "freshness_seconds": 1.2
}
```

---

## 4. Table: `rejected_sensor_data` (Quarantine Table)
Stores records that failed structural, schema, or physical possibility validation checks.

| Column Name | Data Type | Nullable | Key / Constraint | Description | Example Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `rejection_id` | INTEGER | No | PRIMARY KEY (AUTO) | Sequential quarantine identifier | `1` |
| `event_id` | VARCHAR(100) | Yes | INDEX | Source event identifier if available | `"evt_corrupt_99"` |
| `sensor_id` | VARCHAR(50) | Yes | INDEX | Sensor ID if extractable | `"S015"` |
| `raw_payload` | TEXT | No | | Complete payload string of rejected record | `{"bad_ts": "..."}` |
| `rejection_reason` | TEXT | No | | Explicit category and error explanation | `"MALFORMED_TIMESTAMP"` |
| `rejection_timestamp` | DATETIME | No | DEFAULT UTC | Timestamp when record was quarantined | `2026-10-13 10:15:35` |

**Index**: `idx_rejected_time (rejection_timestamp)`

---

## 5. Table: `machine_health_alerts`
Stores operational threshold violations and anomaly signals.

| Column Name | Data Type | Nullable | Key / Constraint | Description | Example Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `alert_id` | VARCHAR(100) | No | PRIMARY KEY | Unique alert identifier | `"alt_8f2e4c1a"` |
| `sensor_id` | VARCHAR(50) | No | INDEX | Affected sensor | `"S005"` |
| `machine_id` | VARCHAR(50) | No | INDEX | Affected machine | `"M01"` |
| `event_id` | VARCHAR(100) | No | INDEX | Originating telemetry event ID | `"evt_a9b1c2d3"` |
| `alert_type` | VARCHAR(50) | No | | Alert type (`TEMP_HIGH`, `PRESSURE_DROP`, etc.) | `"TEMP_HIGH"` |
| `severity` | VARCHAR(20) | No | | Severity level (`CRITICAL`, `WARNING`, `INFO`) | `"CRITICAL"` |
| `measured_value` | FLOAT | Yes | | Actual reading value triggering the alert | `94.8` |
| `configured_threshold` | FLOAT | Yes | | Configured limit threshold breached | `85.0` |
| `alert_timestamp` | DATETIME | No | INDEX | Time when anomaly occurred | `2026-10-13 10:15:30` |
| `alert_status` | VARCHAR(20) | No | DEFAULT 'ACTIVE' | Status (`ACTIVE`, `ACKNOWLEDGED`, `RESOLVED`)| `"ACTIVE"` |

**Composite Constraints & Indexes**:
- Unique Constraint: `uq_event_alert_type (event_id, alert_type)`
- Composite Index: `idx_alerts_machine_time (machine_id, alert_timestamp)`

---

## 6. Table: `pipeline_runs`
Stores execution cycle performance, record throughput, and audit logs.

| Column Name | Data Type | Nullable | Key / Constraint | Description | Example Value |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `run_id` | VARCHAR(100) | No | PRIMARY KEY | Unique run identifier | `"run_33099e643e3c"` |
| `start_timestamp` | DATETIME | No | DEFAULT UTC | Execution initiation timestamp | `2026-10-13 10:15:30` |
| `end_timestamp` | DATETIME | Yes | | Execution completion timestamp | `2026-10-13 10:15:31` |
| `execution_status` | VARCHAR(30) | No | | Status (`RUNNING`, `COMPLETED`, `FAILED`) | `"COMPLETED"` |
| `records_received` | INTEGER | No | DEFAULT 0 | Total records entering pipeline cycle | `200` |
| `records_processed` | INTEGER | No | DEFAULT 0 | Valid records transformed and persisted | `192` |
| `records_rejected` | INTEGER | No | DEFAULT 0 | Defective records quarantined | `8` |
| `error_count` | INTEGER | No | DEFAULT 0 | Unhandled system exceptions encountered | `0` |
| `execution_summary`| TEXT | Yes | | JSON string with stage timings and metrics | `{"duration_seconds": 0.33, ...}` |
