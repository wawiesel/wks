"""Database API module."""

from .Database import Database
from ..schema_loader import register_from_schema

_models = register_from_schema("database")
DatabaseListOutput = _models.get("DatabaseListOutput")
DatabaseShowOutput = _models.get("DatabaseShowOutput")
DatabaseResetOutput = _models.get("DatabaseResetOutput")

__all__ = [
    "Database",
    "DatabaseListOutput",
    "DatabaseShowOutput",
    "DatabaseResetOutput",
]
