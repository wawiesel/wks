"""Config API module."""

from .WKSConfig import WKSConfig
from ..schema_loader import register_from_schema

_models = register_from_schema("config")
ConfigListOutput = _models["ConfigListOutput"]
ConfigShowOutput = _models["ConfigShowOutput"]
ConfigVersionOutput = _models["ConfigVersionOutput"]

__all__ = [
    "WKSConfig",
    "ConfigListOutput",
    "ConfigShowOutput",
    "ConfigVersionOutput"
]
