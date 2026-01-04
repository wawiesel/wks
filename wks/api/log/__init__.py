"""Log module - centralized logging."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
LogPruneOutput: type[BaseModel] = _models["LogPruneOutput"]
LogStatusOutput: type[BaseModel] = _models["LogStatusOutput"]

__all__ = [
    "LogPruneOutput",
    "LogStatusOutput",
]
