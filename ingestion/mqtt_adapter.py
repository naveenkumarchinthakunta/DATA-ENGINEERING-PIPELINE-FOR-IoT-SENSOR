"""
MQTT Industrial Gateway Adapter.
Parses telemetry messages arriving over industrial MQTT topics, standardizes payloads,
and routes them into the Data Ingestion Service.
Topic hierarchy standard: factory/{zone}/{machine_id}/{sensor_id}/telemetry
"""

from datetime import datetime, timezone
import json
from typing import Dict, Any, Optional
from ingestion.ingestion_service import IngestionService, IngestionResult
from monitoring.logging_config import logger


class MQTTMessagePayload:
    """Represents an incoming MQTT packet."""
    def __init__(self, topic: str, payload_bytes: bytes):
        self.topic = topic
        self.payload_bytes = payload_bytes


class MQTTGatewayAdapter:
    """
    Translates incoming MQTT messages into standardized pipeline records.
    Designed for integration with paho-mqtt or enterprise message brokers (Mosquitto, EMQX).
    """

    def __init__(self, ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service

    def parse_topic(self, topic: str) -> Dict[str, str]:
        """
        Parses topic formatted as: factory/{zone}/{machine_id}/{sensor_id}/telemetry
        """
        parts = topic.strip("/").split("/")
        if len(parts) >= 5 and parts[0] == "factory" and parts[4] == "telemetry":
            return {
                "factory_zone": parts[1],
                "machine_id": parts[2],
                "sensor_id": parts[3],
            }
        return {}

    def process_message(self, topic: str, payload_str: str) -> IngestionResult:
        """
        Parses topic and payload, injects metadata if missing, and submits to ingestion.
        """
        try:
            data = json.loads(payload_str)
        except Exception as e:
            logger.error("MQTT payload is not valid JSON from topic %s: %s", topic, e)
            return IngestionResult(received=1, failed=1, errors=[f"JSON parse error: {str(e)}"])

        topic_meta = self.parse_topic(topic)
        if topic_meta:
            data.setdefault("factory_zone", topic_meta["factory_zone"])
            data.setdefault("machine_id", topic_meta["machine_id"])
            data.setdefault("sensor_id", topic_meta["sensor_id"])

        if "ingestion_timestamp" not in data:
            data["ingestion_timestamp"] = datetime.now(timezone.utc).isoformat()

        return self.ingestion_service.ingest_record(data)


# Simulation Helper for MQTT edge gateway testing
def simulate_mqtt_publish(adapter: MQTTGatewayAdapter, sensor_id: str, machine_id: str, zone: str, temp: float, press: float, vib: float):
    import uuid
    topic = f"factory/{zone}/{machine_id}/{sensor_id}/telemetry"
    payload = {
        "event_id": f"evt_mqtt_{uuid.uuid4().hex[:8]}",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_celsius": temp,
        "pressure_bar": press,
        "vibration_mm_s": vib,
    }
    return adapter.process_message(topic, json.dumps(payload))
