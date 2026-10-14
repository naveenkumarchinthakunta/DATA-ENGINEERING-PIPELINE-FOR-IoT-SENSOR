"""
IoT Sensor Simulation Engine.
Simulates 200 uniquely identified industrial sensors generating temperature, pressure,
and vibration telemetry across multiple factory zones and machines.
Supports deterministic runs (seeded), continuous execution, configurable anomaly injection,
and deliberate quality fault injection for pipeline validation testing.
"""

from datetime import datetime, timezone, timedelta
import random
import uuid
from typing import List, Dict, Any, Optional
from config.settings import settings
from monitoring.logging_config import logger


class SensorSimulator:
    """
    Simulates factory IoT sensor network (200 sensors by default).
    Generates plausible industrial telemetry with physics-inspired baselines,
    random walks, periodic cycles, operational anomalies, and deliberate data quality faults.
    """

    def __init__(
        self,
        total_sensors: int = 200,
        total_machines: int = 20,
        seed: Optional[int] = None,
        anomaly_rate: Optional[float] = None,
        quality_fault_rate: Optional[float] = None,
    ):
        self.total_sensors = total_sensors
        self.total_machines = total_machines
        self.anomaly_rate = (
            anomaly_rate if anomaly_rate is not None else settings.simulation.anomaly_rate
        )
        self.quality_fault_rate = (
            quality_fault_rate
            if quality_fault_rate is not None
            else settings.simulation.quality_fault_rate
        )
        self.rng = random.Random(seed)

        # Baseline operating parameters per machine
        self.machine_baselines: Dict[str, Dict[str, float]] = {}
        for m in range(1, self.total_machines + 1):
            m_id = f"M{m:02d}"
            self.machine_baselines[m_id] = {
                "base_temp": 45.0 + self.rng.uniform(-5.0, 15.0),    # Normal range ~40 - 60 °C
                "base_press": 4.5 + self.rng.uniform(-1.0, 2.0),     # Normal range ~3.5 - 6.5 bar
                "base_vib": 1.2 + self.rng.uniform(-0.3, 0.8),       # Normal range ~0.9 - 2.0 mm/s
                "temp_max": 85.0,
                "temp_min": 20.0,
                "press_max": 10.0,
                "press_min": 1.0,
                "vib_max": 5.0,
                "vib_min": 0.0,
            }

        # Initialize 200 Sensor Metadata records
        self.sensors_metadata: List[Dict[str, Any]] = self._build_sensor_metadata()
        self._last_readings: Dict[str, Dict[str, float]] = {}

    def _build_sensor_metadata(self) -> List[Dict[str, Any]]:
        """Construct deterministic sensor registry metadata for S001 through S200."""
        zones = settings.simulation.factory_zones
        sensors = []

        for i in range(1, self.total_sensors + 1):
            sensor_id = f"S{i:03d}"
            machine_num = ((i - 1) % self.total_machines) + 1
            machine_id = f"M{machine_num:02d}"
            zone = zones[(machine_num - 1) % len(zones)]

            # A small fraction (e.g. 5%) might be marked INACTIVE or MAINTENANCE initially
            status = "ACTIVE"
            if i in (198, 199):
                status = "INACTIVE"
            elif i == 200:
                status = "MAINTENANCE"

            m_base = self.machine_baselines[machine_id]
            sensors.append(
                {
                    "sensor_id": sensor_id,
                    "machine_id": machine_id,
                    "factory_zone": zone,
                    "sensor_status": status,
                    "temperature_limit_min": m_base["temp_min"],
                    "temperature_limit_max": m_base["temp_max"],
                    "pressure_limit_min": m_base["press_min"],
                    "pressure_limit_max": m_base["press_max"],
                    "vibration_limit_min": m_base["vib_min"],
                    "vibration_limit_max": m_base["vib_max"],
                }
            )
        return sensors

    def get_registered_sensors(self) -> List[Dict[str, Any]]:
        """Return the pre-configured sensor metadata list."""
        return self.sensors_metadata

    def generate_single_reading(
        self,
        sensor_meta: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        inject_anomaly: bool = False,
        inject_quality_fault: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a single telemetry event for a given sensor.
        Distinguishes between valid readings, operational anomalies, and data quality faults.
        """
        event_time = timestamp or datetime.now(timezone.utc)
        sensor_id = sensor_meta["sensor_id"]
        machine_id = sensor_meta["machine_id"]
        zone = sensor_meta["factory_zone"]
        m_base = self.machine_baselines[machine_id]

        event_id = f"evt_{uuid.uuid4().hex[:12]}"

        # Base physical values with small stochastic fluctuations
        temp = round(m_base["base_temp"] + self.rng.gauss(0, 1.5), 2)
        press = round(m_base["base_press"] + self.rng.gauss(0, 0.25), 2)
        vib = round(max(0.05, m_base["base_vib"] + self.rng.gauss(0, 0.15)), 2)

        # Operational Anomaly (valid data type and structure, but value outside normal machine thresholds)
        if inject_anomaly:
            anomaly_type = self.rng.choice(["TEMP_SPIKE", "PRESSURE_HIGH", "VIBRATION_SPIKE", "PRESSURE_DROP"])
            if anomaly_type == "TEMP_SPIKE":
                temp = round(m_base["temp_max"] + self.rng.uniform(5.0, 25.0), 2)  # E.g. 95°C
            elif anomaly_type == "PRESSURE_HIGH":
                press = round(m_base["press_max"] + self.rng.uniform(1.0, 5.0), 2) # E.g. 12 bar
            elif anomaly_type == "VIBRATION_SPIKE":
                vib = round(m_base["vib_max"] + self.rng.uniform(1.5, 6.0), 2)     # E.g. 8.5 mm/s
            elif anomaly_type == "PRESSURE_DROP":
                press = round(max(0.1, m_base["press_min"] - self.rng.uniform(0.5, 0.9)), 2) # E.g. 0.3 bar

        # Construct standard valid record
        record: Dict[str, Any] = {
            "event_id": event_id,
            "sensor_id": sensor_id,
            "machine_id": machine_id,
            "factory_zone": zone,
            "event_timestamp": event_time.isoformat(),
            "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
            "temperature_celsius": temp,
            "pressure_bar": press,
            "vibration_mm_s": vib,
            "is_simulated": True,
        }

        # Data Quality Fault injection (creates malformed records to test quarantine engine)
        if inject_quality_fault:
            fault_type = self.rng.choice([
                "MISSING_SENSOR_ID",
                "MALFORMED_TIMESTAMP",
                "FUTURE_TIMESTAMP",
                "INVALID_NUMERIC_TYPE",
                "NAN_MEASUREMENT",
                "MISSING_EVENT_ID",
            ])
            if fault_type == "MISSING_SENSOR_ID":
                record["sensor_id"] = None
            elif fault_type == "MALFORMED_TIMESTAMP":
                record["event_timestamp"] = "2026-INVALID-DATE 99:99"
            elif fault_type == "FUTURE_TIMESTAMP":
                record["event_timestamp"] = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
            elif fault_type == "INVALID_NUMERIC_TYPE":
                record["temperature_celsius"] = "ERROR_STRING_NOT_NUMBER"
            elif fault_type == "NAN_MEASUREMENT":
                record["pressure_bar"] = float("nan")
            elif fault_type == "MISSING_EVENT_ID":
                del record["event_id"]

        return record

    def generate_batch(
        self,
        batch_size: Optional[int] = None,
        timestamp: Optional[datetime] = None,
        include_duplicates: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Generates telemetry records across sensors in the network.
        Optionally injects occasional duplicates to test deduplication logic.
        """
        size = batch_size if batch_size is not None else self.total_sensors
        base_time = timestamp or datetime.now(timezone.utc)
        batch = []

        # Sample or iterate over sensors
        sensors_to_sample = self.sensors_metadata[:size]

        for s_meta in sensors_to_sample:
            # Skip readings if sensor is marked INACTIVE (simulates disconnected sensor)
            if s_meta.get("sensor_status") == "INACTIVE" and self.rng.random() > 0.1:
                continue

            inject_anomaly = self.rng.random() < self.anomaly_rate
            inject_quality = self.rng.random() < self.quality_fault_rate

            record = self.generate_single_reading(
                s_meta,
                timestamp=base_time,
                inject_anomaly=inject_anomaly,
                inject_quality_fault=inject_quality,
            )
            batch.append(record)

        # Inject an intentional duplicate event_id record if requested and batch not empty
        if include_duplicates and batch and self.rng.random() < 0.2:
            duplicate_record = dict(batch[0])
            batch.append(duplicate_record)

        return batch
