import logging
import sys
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("newpod")

def setup_telemetry(app: FastAPI) -> None:
    # Set up OpenTelemetry tracer provider
    provider = TracerProvider()
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Instrument FastAPI app
    FastAPIInstrumentor.instrument_app(app)

    # Instrument with Prometheus metrics
    Instrumentator().instrument(app).expose(app)

    logger.info("OpenTelemetry and Prometheus metrics initialized.")
