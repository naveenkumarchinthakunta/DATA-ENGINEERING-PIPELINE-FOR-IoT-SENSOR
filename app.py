"""
Flask Backend Web Application for IoT Data Engineering Pipeline.
Provides RESTful APIs for serving real-time telemetry, aggregations, alerts, and data quality metrics.
"""

from flask import Flask, jsonify, request
from api.routes import api_bp
from api.ui_routes import ui_bp
from storage.database import init_db
from config.settings import settings
from monitoring.logging_config import logger


def create_app() -> Flask:
    """Application factory for Flask Web App and API."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["JSON_SORT_KEYS"] = False

    # Initialize database tables on app startup
    init_db()

    # Register API routes and UI routes
    app.register_blueprint(api_bp)
    app.register_blueprint(ui_bp)

    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({
                "status": "error",
                "error_code": "RESOURCE_NOT_FOUND",
                "message": "The requested API endpoint or resource was not found.",
            }), 404
        return "<h3>404 - Industrial Telemetry Resource Not Found</h3><p><a href='/'>Return to Factory Overview</a></p>", 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return jsonify({
            "status": "error",
            "error_code": "METHOD_NOT_ALLOWED",
            "message": "HTTP method not allowed for this endpoint.",
        }), 405

    @app.errorhandler(500)
    def handle_internal_error(e):
        logger.error("Internal Server Error: %s", e)
        return jsonify({
            "status": "error",
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected internal server error occurred.",
        }), 500

    @app.route("/api")
    def api_index():
        return jsonify({
            "title": "IoT Sensor Data Engineering Pipeline API",
            "version": "1.0.0",
            "status": "ONLINE",
            "endpoints": [
                "/api/health",
                "/api/sensors",
                "/api/sensors/<sensor_id>/readings",
                "/api/machines/<machine_id>/summary",
                "/api/analytics/summary",
                "/api/analytics/window",
                "/api/alerts",
                "/api/pipeline/runs",
                "/api/data-quality/summary",
                "/api/pipeline/trigger",
            ],
        })

    return app


app = create_app()

if __name__ == "__main__":
    logger.info("Starting Flask API server on http://%s:%d", settings.api.host, settings.api.port)
    app.run(
        host=settings.api.host,
        port=settings.api.port,
        debug=settings.api.debug,
    )
