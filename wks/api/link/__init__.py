"""Link API domain."""

from pydantic import BaseModel

# Registers the domain's output schemas
from ..config.schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
LinkCheckOutput: type[BaseModel] = _models["LinkCheckOutput"]
LinkShowOutput: type[BaseModel] = _models["LinkShowOutput"]
LinkStatusOutput: type[BaseModel] = _models["LinkStatusOutput"]
LinkSyncOutput: type[BaseModel] = _models["LinkSyncOutput"]

__all__ = [
    "LinkCheckOutput",
    "LinkShowOutput",
    "LinkStatusOutput",
    "LinkSyncOutput",
]
