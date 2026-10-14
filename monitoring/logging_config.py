"""
Structured logging configuration for IoT Data Engineering Pipeline.
Sets up formatters and handlers with timestamps, log levels, module names, and file outputs.
"""

import logging
import sys
from pathlib import Path
from config.settings import settings


def setup_logging(name: str = "iot_pipeline") -> logging.Logger:
    """Configure and return a structured logger."""
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    log_level = getattr(logging, settings.logging.level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Standard format: timestamp | level | module:line | message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

    # File Handler
    try:
        log_file_path = Path(settings.logging.log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning("Could not initialize file log handler at %s: %s", settings.logging.log_file, e)

    return logger


# Global logger instance
logger = setup_logging()
