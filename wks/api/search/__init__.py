"""Search API module."""

from ..config.schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
SearchOutput = _models["SearchOutput"]

__all__ = ["SearchOutput"]
