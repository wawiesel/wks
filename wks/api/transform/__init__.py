"""Transform API module."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_schema("transform")
TransformEngineOutput: type[BaseModel] = _models["TransformEngineOutput"]

__all__ = [
    "TransformEngineOutput",
]
