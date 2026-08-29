from pythonjsonlogger.json import JsonFormatter

from config import settings
import logging
import sys


def setup_logging() -> None:
    """Structured JSON logs so Promtail / Datadog can parse fields reliably."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(service)s %(env)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.service = settings.app_name
        record.env = settings.app_env
        return record

    logging.setLogRecordFactory(record_factory)