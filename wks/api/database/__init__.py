"""Database API module."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
DatabaseListOutput: type[BaseModel] = _models["DatabaseListOutput"]
DatabaseShowOutput: type[BaseModel] = _models["DatabaseShowOutput"]
DatabaseResetOutput: type[BaseModel] = _models["DatabaseResetOutput"]
DatabasePruneOutput: type[BaseModel] = _models["DatabasePruneOutput"]


__all__ = [
    "DatabaseListOutput",
    "DatabasePruneOutput",
    "DatabaseResetOutput",
    "DatabaseShowOutput",
]
