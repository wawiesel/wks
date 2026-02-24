"""Mv API module."""

from pydantic import BaseModel

from ..config.schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
MvMvOutput: type[BaseModel] = _models["MvMvOutput"]

__all__ = ["MvMvOutput"]
