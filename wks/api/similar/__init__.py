"""Similar API module."""

from pydantic import BaseModel

from ..config.schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
SimilarOutput: type[BaseModel] = _models["SimilarOutput"]

__all__ = ["SimilarOutput"]
