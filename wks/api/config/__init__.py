"""Config API module."""

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
ConfigListOutput = _models["ConfigListOutput"]
ConfigShowOutput = _models["ConfigShowOutput"]
ConfigVersionOutput = _models["ConfigVersionOutput"]

__all__ = ["ConfigListOutput", "ConfigShowOutput", "ConfigVersionOutput"]
