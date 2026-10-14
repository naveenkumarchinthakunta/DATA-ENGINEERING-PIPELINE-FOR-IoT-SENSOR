# API Reference: IoT Sensor Data Engineering Pipeline

The Flask REST API provides programmatic access to sensor configurations, raw & processed telemetry, machine aggregations, operational alarms, quarantine statistics, and pipeline execution controls.

**Base URL**: `http://127.0.0.1:5000/api`

---

## Standard Response Structure

All endpoints return a uniform JSON envelope:

### Successful Response:
```json
{
  "status": "success",
  "message": "Operation completed successfully",
  "data": { ... },
  "timestamp": "2026-10-13T10:30:00.000000+00:00"
}
```

### Error Response:
```json
{
  "status": "error",
  "error_code": "RESOURCE_NOT_FOUND",
  "message": "Detailed description of the error",
  "timestamp": "2026-10-13T10:30:00.000000+00:00"
}
```

---

## Endpoints

### 1. `GET /api/health`
Checks application and database connectivity.

#### Example Request:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health" -Method Get
```

#### Example Response (200 OK):
```json
{
  "status": "success",
  "message": "Service is HEALTHY",
  "data": {
    "application_status": "HEALTHY",
    "database_connected": true,
    "environment": "production-ready local"
  },
  "timestamp": "2026-10-13T10:30:00+00:00"
}
```

---

### 2. `GET /api/sensors`
Retrieves registered sensors, their assigned machine, factory zone, status, and operating limits.

#### Query Parameters:
- `zone` *(optional, string)*: Filter by factory zone (e.g., `Zone-North`)
- `status` *(optional, string)*: Filter by status (`ACTIVE`, `INACTIVE`, `MAINTENANCE`)

#### Example Request:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/sensors?zone=Zone-North&status=ACTIVE" -Method Get
```

#### Example Response (200 OK):
```json
{
  "status": "success",
  "message": "Success",
  "data": {
    "total": 50,
    "sensors": [
      {
        "sensor_id": "S001",
        "machine_id": "M01",
        "factory_zone": "Zone-North",
        "sensor_status": "ACTIVE",
        "temperature_limit_min": 20.0,
        "temperature_limit_max": 85.0,
        "pressure_limit_min": 1.0,
        "pressure_limit_max": 10.0,
        "vibration_limit_min": 0.0,
        "vibration_limit_max": 5.0,
        "created_at": "2026-10-13T10:17:46",
        "updated_at": "2026-10-13T10:17:46"
      }
    ]
  },
  "timestamp": "2026-10-13T10:30:00+00:00"
}
```

---

### 3. `GET /api/sensors/<sensor_id>/readings`
Fetches paginated historical readings for a specified sensor.

#### Query Parameters:
- `page` *(optional, int, default 1)*: Page number
- `per_page` *(optional, int, default 50, max 500)*: Items per page
- `start_time` *(optional, ISO string)*: Filter readings after this UTC time
- `end_time` *(optional, ISO string)*: Filter readings before this UTC time

#### Example Request:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/sensors/S001/readings?page=1&per_page=2" -Method Get
```

#### Example Response (200 OK):
```json
{
  "status": "success",
  "message": "Success",
  "data": {
    "sensor_id": "S001",
    "page": 1,
    "per_page": 2,
    "total_records": 12,
    "readings": [
      {
        "event_id": "evt_4a2d8f1e9c3b",
        "sensor_id": "S001",
        "machine_id": "M01",
        "event_timestamp": "2026-10-13T10:46:01",
        "temperature_celsius": 48.35,
        "pressure_bar": 4.62,
        "vibration_mm_s": 1.15,
        "validation_status": "VALID",
        "transformation_timestamp": "2026-10-13T10:46:02",
        "quality_flags": "{\"temp_deviation\": -4.15, \"press_deviation\": -0.88, \"vib_deviation\": -0.35, \"freshness_seconds\": 1.2}"
      }
    ]
  },
  "timestamp": "2026-10-13T10:30:00+00:00"
}
```

---

### 4. `GET /api/machines/<machine_id>/summary`
Returns roll-up statistical summaries for a machine.

#### Example Request:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/machines/M01/summary" -Method Get
```

#### Example Response (200 OK):
```json
{
  "status": "success",
  "message": "Success",
  "data": {
    "machine_id": "M01",
    "total_readings": 120,
    "temperature": {
      "avg": 49.82,
      "min": 41.20,
      "max": 96.40,
      "std": 7.35
    },
    "pressure": {
      "avg": 4.88,
      "min": 2.15,
      "max": 9.40,
      "std": 1.12
    },
    "vibration": {
      "avg": 1.35,
      "min": 0.45,
      "max": 6.80,
      "std": 0.88
    },
    "total_alerts": 8
  },
  "timestamp": "2026-10-13T10:30:00+00:00"
}
```

---

### 5. `GET /api/analytics/summary`
Returns global KPIs, active/inactive sensor status, and overall pipeline yield.

#### Query Parameters:
- `window_minutes` *(optional, int, default 5)*: Time window for determining active sensor status

#### Example Request:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/analytics/summary?window_minutes=5" -Method Get
```

#### Example Response (200 OK):
```json
{
  "status": "success",
  "message": "Success",
  "data": {
    "total_registered_sensors": 200,
    "active_sensors": 197,
    "inactive_sensors": 3,
    "reporting_window_minutes": 5,
    "total_raw_records": 1184,
    "total_processed_records": 1138,
    "total_rejected_records": 46,
    "validation_success_rate": 96.11,
    "data_rejection_rate": 3.89,
    "temperature_stats": {
      "avg": 52.48,
      "min": 38.12,
      "max": 108.45
    },
    "pressure_stats": {
      "avg": 5.12,
      "min": 0.28,
      "max": 13.62
    },
    "vibration_stats": {
      "avg": 1.74,
      "min": 0.35,
      "max": 10.82
    },
    "total_alerts": 102,
    "active_alerts": 101,
    "pipeline_runs_count": 9,
    "pipeline_success_rate": 100.0,
    "last_successful_run": "2026-10-13T10:48:03"
  },
  "timestamp": "2026-10-13T10:30:00+00:00"
}
```

---

### 6. `GET /api/analytics/window`
Aggregates telemetry across configurable time buckets (1min, 5min, 15min, 1hour).

#### Query Parameters:
- `window` *(optional, string, default "5min")*: `1min`, `5min`, `15min`, `1hour`
- `sensor_id` *(optional, string)*: Filter by sensor
- `machine_id` *(optional, string)*: Filter by machine

#### Example Request:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/analytics/window?window=5min&sensor_id=S001" -Method Get
```

---

### 7. `GET /api/alerts`
Returns machine health alerts with severity, status, and machine filters.

#### Query Parameters:
- `severity` *(optional, string)*: `CRITICAL`, `WARNING`, `INFO`
- `status` *(optional, string)*: `ACTIVE`, `ACKNOWLEDGED`, `RESOLVED`
- `machine_id` *(optional, string)*: Filter by machine ID
- `sensor_id` *(optional, string)*: Filter by sensor ID
- `page` *(optional, int, default 1)*
- `per_page` *(optional, int, default 50)*

#### Example Request:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/alerts?severity=CRITICAL&status=ACTIVE" -Method Get
```

---

### 8. `POST /api/alerts/<alert_id>/acknowledge`
Marks an active alert as acknowledged.

#### Example Request:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/alerts/alt_8f2e4c1a/acknowledge" -Method Post
```

#### Example Response (200 OK):
```json
{
  "status": "success",
  "message": "Success",
  "data": {
    "alert_id": "alt_8f2e4c1a",
    "status": "ACKNOWLEDGED"
  },
  "timestamp": "2026-10-13T10:30:00+00:00"
}
```

---

### 9. `GET /api/data-quality/summary`
Returns validation pass/fail rates, quarantine counts, and categorized failure reasons.

#### Example Request:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/data-quality/summary" -Method Get
```

#### Example Response (200 OK):
```json
{
  "status": "success",
  "message": "Success",
  "data": {
    "total_valid_records": 1138,
    "total_rejected_records": 46,
    "pass_rate_percentage": 96.11,
    "reasons_breakdown": [
      { "reason": "MALFORMED_TIMESTAMP", "count": 14 },
      { "reason": "SCHEMA_VALIDATION_ERROR: Missing sensor_id", "count": 12 },
      { "reason": "FUTURE_TIMESTAMP_EXCEEDED_SKEW", "count": 9 },
      { "reason": "SCHEMA_VALIDATION_ERROR: NaN or Infinite", "count": 7 },
      { "reason": "NEGATIVE_ABSOLUTE_PRESSURE", "count": 4 }
    ],
    "recent_rejections": [ ... ]
  },
  "timestamp": "2026-10-13T10:30:00+00:00"
}
```

---

### 10. `POST /api/pipeline/trigger`
Triggers an on-demand ingestion and transformation cycle.

#### Request Body:
```json
{
  "batch_size": 200
}
```

#### Example Request:
```powershell
$body = @{ batch_size = 200 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/pipeline/trigger" -Method Post -Body $body -ContentType "application/json"
```
