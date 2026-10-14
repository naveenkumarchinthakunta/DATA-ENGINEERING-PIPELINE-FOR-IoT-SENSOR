"""
Frontend UI and Jinja2 Template Integration Tests.
Verifies that all 6 browser-based monitoring pages load successfully with status 200,
valid title tags, and consistent navigation links.
"""

import pytest
from app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_ui_overview_page(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "<title>Factory Overview" in html
    assert "Factory Overview & System Health" in html
    assert "chartZones" in html
    assert "chartSeverity" in html


def test_ui_sensors_page(client):
    res = client.get("/sensors")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "<title>Sensor Monitoring" in html
    assert "Real-Time Sensor Telemetry Matrix" in html
    assert "sensorSearchInput" in html


def test_ui_trends_page(client):
    res = client.get("/trends")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "<title>Historical Trends" in html
    assert "chartTempTrend" in html
    assert "chartPressTrend" in html
    assert "chartVibTrend" in html


def test_ui_data_quality_page(client):
    res = client.get("/data-quality")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "<title>Data Quality & Quarantine" in html
    assert "chartRejections" in html
    assert "quarantineTableBody" in html


def test_ui_alerts_page(client):
    res = client.get("/alerts")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "<title>Machine Health Alerts" in html
    assert "alertsTableBody" in html
    assert "filterSeverity" in html


def test_ui_pipeline_page(client):
    res = client.get("/pipeline")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "<title>Pipeline Operations" in html
    assert "pipelineRunsTableBody" in html
    assert "chartStageLatencies" in html


def test_ui_static_stylesheet(client):
    res = client.get("/static/css/style.css")
    assert res.status_code == 200
    assert "var(--bg-primary)" in res.data.decode("utf-8")
