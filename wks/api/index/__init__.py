"""Index API module."""

from ..config.schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
IndexOutput = _models["IndexOutput"]
IndexStatusOutput = _models["IndexStatusOutput"]
IndexAutoOutput = _models["IndexAutoOutput"]

__all__ = ["IndexAutoOutput", "IndexOutput", "IndexStatusOutput"]
