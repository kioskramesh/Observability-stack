import os


class Settings:
    app_name: str = os.getenv("APP_NAME", "order-service")
    app_env: str = os.getenv("APP_ENV", "local")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    otel_endpoint: str = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
    )
    # Chaos toggles (also controllable via /chaos endpoints)
    fail_rate: float = float(os.getenv("FAIL_RATE", "0"))
    latency_ms: int = int(os.getenv("LATENCY_MS", "0"))


settings = Settings()