"""Transform API module."""

from wks.api.config.output_models import output_model

# Maximum iterations for generator consumption loops.
# Prevents infinite loops from mutation testing or bugs.
MAX_GENERATOR_ITERATIONS = 10000

TransformEngineOutput = output_model(
    "TransformEngineOutput",
    "source_uri",
    "destination_uri",
    "engine",
    "status",
    "checksum",
    "output_content",
    "processing_time_ms",
    "cached",
)
TransformListOutput = output_model("TransformListOutput", "default_engine", "engines")
TransformInfoOutput = output_model("TransformInfoOutput", "engine", "config")

__all__ = [
    "MAX_GENERATOR_ITERATIONS",
    "TransformEngineOutput",
    "TransformInfoOutput",
    "TransformListOutput",
]
