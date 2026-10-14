"""
Settings and configuration management for IoT Data Engineering Pipeline.
Loads environment variables and provides centralized access with type safety and defaults.
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if it exists
load_dotenv(BASE_DIR / ".env")


@dataclass
class DatabaseSettings:
    url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'iot_pipeline.db'}"
        )
    )
    echo: bool = field(
        default_factory=lambda: os.getenv("DATABASE_ECHO", "False").lower() in ("true", "1", "yes")
    )


@dataclass
class SimulationSettings:
    total_sensors: int = field(
        default_factory=lambda: int(os.getenv("TOTAL_SENSORS", "200"))
    )
    total_machines: int = field(
        default_factory=lambda: int(os.getenv("TOTAL_MACHINES", "20"))
    )
    batch_size: int = field(
        default_factory=lambda: int(os.getenv("SIMULATION_BATCH_SIZE", "200"))
    )
    interval_seconds: int = field(
        default_factory=lambda: int(os.getenv("SIMULATION_INTERVAL_SECONDS", "5"))
    )
    # Probability of generating operational anomalies (measurements crossing limits)
    anomaly_rate: float = field(
        default_factory=lambda: float(os.getenv("ANOMALY_RATE", "0.08"))
    )
    # Probability of generating data quality faults (corrupt timestamp, missing value, duplicate)
    quality_fault_rate: float = field(
        default_factory=lambda: float(os.getenv("QUALITY_FAULT_RATE", "0.05"))
    )
    # Configurable factory zones
    factory_zones: list[str] = field(
        default_factory=lambda: ["Zone-North", "Zone-East", "Zone-South", "Zone-West"]
    )


@dataclass
class QualityAndAlertSettings:
    # Machine baseline operating ranges (demonstration defaults)
    default_temp_min: float = 20.0
    default_temp_max: float = 85.0
    default_pressure_min: float = 1.0
    default_pressure_max: float = 10.0
    default_vibration_min: float = 0.0
    default_vibration_max: float = 5.0

    # Rate of change threshold (per reading interval)
    temp_rate_of_change_threshold: float = 15.0
    pressure_rate_of_change_threshold: float = 3.0
    vibration_rate_of_change_threshold: float = 2.5

    # Freshness threshold (minutes after which sensor is marked inactive / stale)
    reporting_window_minutes: int = field(
        default_factory=lambda: int(os.getenv("REPORTING_WINDOW_MINUTES", "5"))
    )
    stale_sensor_threshold_minutes: int = field(
        default_factory=lambda: int(os.getenv("STALE_SENSOR_THRESHOLD_MINUTES", "10"))
    )
    # Future timestamp tolerance in seconds
    max_future_skew_seconds: int = 120


@dataclass
class APISettings:
    host: str = field(default_factory=lambda: os.getenv("API_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "5000")))
    debug: bool = field(
        default_factory=lambda: os.getenv("API_DEBUG", "False").lower() in ("true", "1", "yes")
    )


@dataclass
class DashboardSettings:
    port: int = field(default_factory=lambda: int(os.getenv("DASHBOARD_PORT", "8501")))
    auto_refresh_seconds: int = field(
        default_factory=lambda: int(os.getenv("AUTO_REFRESH_SECONDS", "10"))
    )


@dataclass
class LoggingSettings:
    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_file: str = field(
        default_factory=lambda: str(BASE_DIR / os.getenv("LOG_FILE", "data/pipeline.log"))
    )


class Settings:
    """Master application configuration container."""
    def __init__(self):
        self.base_dir = BASE_DIR
        self.db = DatabaseSettings()
        self.simulation = SimulationSettings()
        self.quality = QualityAndAlertSettings()
        self.api = APISettings()
        self.dashboard = DashboardSettings()
        self.logging = LoggingSettings()

    def get_database_uri(self) -> str:
        # Standardize sqlite uri for Windows paths
        url = self.db.url
        if url.startswith("sqlite:///") and "\\" in url:
            url = url.replace("\\", "/")
        return url


# Global singleton settings instance
settings = Settings()
