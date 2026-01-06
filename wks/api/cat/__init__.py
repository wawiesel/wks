"""Cat API module."""

from pydantic import BaseModel

from ..config.schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
CatCmdOutput: type[BaseModel] = _models["CatCmdOutput"]

__all__ = ["CatCmdOutput"]
