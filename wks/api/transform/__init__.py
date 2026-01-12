"""Transform API module."""

from pydantic import BaseModel

from ..config.schema_loader import SchemaLoader

# Maximum iterations for generator consumption loops.
# Prevents infinite loops from mutation testing or bugs.
MAX_GENERATOR_ITERATIONS = 10000

_models = SchemaLoader.register_from_package(__package__)
TransformEngineOutput: type[BaseModel] = _models["TransformEngineOutput"]
TransformListOutput: type[BaseModel] = _models["TransformListOutput"]
TransformInfoOutput: type[BaseModel] = _models["TransformInfoOutput"]

__all__ = [
    "MAX_GENERATOR_ITERATIONS",
    "TransformEngineOutput",
    "TransformInfoOutput",
    "TransformListOutput",
]
