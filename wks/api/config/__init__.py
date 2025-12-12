"""Config API module."""

from .WKSConfig import WKSConfig
from ._load_config import load_config_with_output as load_config_with_output
from ..schema_loader import register_from_schema

_models = register_from_schema("config")
ConfigListOutput = _models["ConfigListOutput"]
ConfigShowOutput = _models["ConfigShowOutput"]
ConfigVersionOutput = _models["ConfigVersionOutput"]

__all__ = [
    "WKSConfig",
    "load_config_with_output",
    "ConfigListOutput",
    "ConfigShowOutput",
    "ConfigVersionOutput"
]
