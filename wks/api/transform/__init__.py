"""Transform API module."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
TransformEngineOutput: type[BaseModel] = _models["TransformEngineOutput"]
TransformListOutput: type[BaseModel] = _models["TransformListOutput"]
TransformInfoOutput: type[BaseModel] = _models["TransformInfoOutput"]

__all__ = [
    "TransformEngineOutput",
    "TransformInfoOutput",
    "TransformListOutput",
]
