"""Database API module."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_schema("database")
DatabaseListOutput: type[BaseModel] = _models["DatabaseListOutput"]
DatabaseShowOutput: type[BaseModel] = _models["DatabaseShowOutput"]
DatabaseResetOutput: type[BaseModel] = _models["DatabaseResetOutput"]

__all__ = [
    "DatabaseListOutput",
    "DatabaseResetOutput",
    "DatabaseShowOutput",
]
