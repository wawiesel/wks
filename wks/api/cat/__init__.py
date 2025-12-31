"""Cat API module."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_schema("cat")
CatCmdOutput: type[BaseModel] = _models["CatCmdOutput"]

__all__ = ["CatCmdOutput"]
