"""Vault API module."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_schema("vault")
VaultStatusOutput: type[BaseModel] = _models["VaultStatusOutput"]
VaultSyncOutput: type[BaseModel] = _models["VaultSyncOutput"]
VaultLinksOutput: type[BaseModel] = _models["VaultLinksOutput"]
VaultCheckOutput: type[BaseModel] = _models["VaultCheckOutput"]

__all__ = [
    "VaultCheckOutput",
    "VaultLinksOutput",
    "VaultStatusOutput",
    "VaultSyncOutput",
]
