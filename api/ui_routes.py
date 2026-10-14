"""
Web UI Routing Blueprint.
Serves HTML5 and Jinja2 templates for the browser-based industrial IoT monitoring cockpit.
"""

from flask import Blueprint, render_template

ui_bp = Blueprint("ui", __name__)


@ui_bp.route("/")
def overview():
    return render_template("index.html", active_page="overview")


@ui_bp.route("/sensors")
def sensors():
    return render_template("sensors.html", active_page="sensors")


@ui_bp.route("/trends")
def trends():
    return render_template("trends.html", active_page="trends")


@ui_bp.route("/data-quality")
def data_quality():
    return render_template("data_quality.html", active_page="data_quality")


@ui_bp.route("/alerts")
def alerts():
    return render_template("alerts.html", active_page="alerts")


@ui_bp.route("/pipeline")
def pipeline():
    return render_template("pipeline.html", active_page="pipeline")
