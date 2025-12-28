"""Transform API module."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_schema("transform")
TransformResultOutput: type[BaseModel] = _models["TransformResultOutput"]

__all__ = [
    "TransformResultOutput",
]
