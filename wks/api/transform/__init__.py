"""Transform API module."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader
from .get_content import get_content

_models = SchemaLoader.register_from_schema("transform")
TransformEngineOutput: type[BaseModel] = _models["TransformEngineOutput"]

__all__ = [
    "TransformEngineOutput",
    "get_content",
]
