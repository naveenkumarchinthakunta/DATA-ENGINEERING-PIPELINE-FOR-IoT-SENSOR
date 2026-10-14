"""
Integration tests for Flask REST API Endpoints.
Verifies response schemas, status codes, query parameter handling, and error states.
"""

import json
import pytest
from app import create_app
from storage.database import init_db, get_db_session
from pipeline.pipeline_runner import PipelineRunner


@pytest.fixture(scope="module")
def test_client():
    init_db()
    # Run a pipeline cycle so test data exists
    runner = PipelineRunner()
    runner.run_cycle(batch_size=50)

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_api_health(test_client):
    res = test_client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["data"]["application_status"] == "HEALTHY"
    assert data["data"]["database_connected"] is True


def test_api_get_sensors(test_client):
    res = test_client.get("/api/sensors")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "sensors" in data["data"]
    assert data["data"]["total"] > 0


def test_api_get_sensors_filter_zone(test_client):
    res = test_client.get("/api/sensors?zone=Zone-North")
    assert res.status_code == 200
    data = res.get_json()
    for s in data["data"]["sensors"]:
        assert s["factory_zone"] == "Zone-North"


def test_api_get_sensor_readings(test_client):
    res = test_client.get("/api/sensors/S001/readings?page=1&per_page=10")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["data"]["sensor_id"] == "S001"
    assert "readings" in data["data"]


def test_api_get_invalid_sensor_readings(test_client):
    res = test_client.get("/api/sensors/S9999_NON_EXISTENT/readings")
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"
    assert data["error_code"] == "NOT_FOUND"


def test_api_get_analytics_summary(test_client):
    res = test_client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    kpis = data["data"]
    assert "total_registered_sensors" in kpis
    assert "validation_success_rate" in kpis
    assert "total_processed_records" in kpis


def test_api_get_alerts(test_client):
    res = test_client.get("/api/alerts?page=1&per_page=20")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "alerts" in data["data"]
    assert "severity_breakdown" in data["data"]


def test_api_get_pipeline_runs(test_client):
    res = test_client.get("/api/pipeline/runs")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["data"]["runs"]) > 0


def test_api_get_data_quality_summary(test_client):
    res = test_client.get("/api/data-quality/summary")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "total_valid_records" in data["data"]
    assert "total_rejected_records" in data["data"]
    assert "pass_rate_percentage" in data["data"]


def test_api_trigger_pipeline(test_client):
    res = test_client.post(
        "/api/pipeline/trigger",
        data=json.dumps({"batch_size": 20}),
        content_type="application/json",
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["data"]["records_received"] >= 20
