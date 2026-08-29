from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from config import settings


def setup_tracing(app) -> None:
    """Export traces via OTLP to the OpenTelemetry Collector.

    The collector can fan out to Tempo (Grafana) and/or Datadog.
    """
    resource = Resource.create(
        {
            "service.name": settings.app_name,
            "service.version": "1.0.0",
            "deployment.environment": settings.app_env,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)


def get_tracer(name: str = __name__):
    return trace.get_tracer(name)