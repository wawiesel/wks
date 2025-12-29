"""Transform API module."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_schema("transform")
TransformTransformOutput: type[BaseModel] = _models["TransformTransformOutput"]

__all__ = [
    "TransformTransformOutput",
]
