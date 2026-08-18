import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

def init_telemetry(app=None):
    """Initializes OpenTelemetry Tracer Provider with Console & OTLP exporters."""
    resource = Resource.create({"service.name": "asyncpm-worker", "service.version": "2.0.0"})
    provider = TracerProvider(resource=resource)
    
    # Console Exporter for local debugging
    console_exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(console_exporter))
    
    trace.set_tracer_provider(provider)
    
    if app:
        FastAPIInstrumentor.instrument_app(app)
        
    print("🔭 [OpenTelemetry] Initialized tracing pipeline for AsyncPM.")
    return trace.get_tracer("asyncpm-tracer")

tracer = trace.get_tracer("asyncpm-tracer")