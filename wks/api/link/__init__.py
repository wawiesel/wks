"""Link API domain."""

from pydantic import BaseModel

# Registers the domain's output schemas
from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_schema("link")
LinkCheckOutput: type[BaseModel] = _models["LinkCheckOutput"]
LinkPruneOutput: type[BaseModel] = _models["LinkPruneOutput"]
LinkShowOutput: type[BaseModel] = _models["LinkShowOutput"]
LinkStatusOutput: type[BaseModel] = _models["LinkStatusOutput"]
LinkSyncOutput: type[BaseModel] = _models["LinkSyncOutput"]

__all__ = [
    "LinkCheckOutput",
    "LinkPruneOutput",
    "LinkShowOutput",
    "LinkStatusOutput",
    "LinkSyncOutput",
]
