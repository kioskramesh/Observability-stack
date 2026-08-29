from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from config import settings
from logging_setup import setup_logging
from routes import chaos, health, orders
from tracing import setup_tracing

setup_logging()

app = FastAPI(
    title="Order Service",
    description="Sample app for learning Prometheus, Grafana, Loki, and Datadog",
    version="1.0.0",
)

setup_tracing(app)

# HTTP RED metrics: Rate, Errors, Duration — classic SRE interview triad
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/metrics", "/health", "/ready"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)

app.include_router(health.router)
app.include_router(orders.router)
app.include_router(chaos.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import logging

    logging.getLogger(__name__).exception(
        "unhandled_exception",
        extra={"path": str(request.url.path), "error": str(exc)},
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "env": settings.app_env,
        "docs": "/docs",
        "metrics": "/metrics",
        "chaos": "/chaos",
    }