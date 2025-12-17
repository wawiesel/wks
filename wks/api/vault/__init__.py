"""Vault API module."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ...utils import expand_path
from ..schema_loader import SchemaLoader
from ._AbstractVault import _AbstractVault
from .obsidian import ObsidianVault

_models = SchemaLoader.register_from_schema("vault")
VaultStatusOutput: type[BaseModel] = _models["VaultStatusOutput"]
VaultSyncOutput: type[BaseModel] = _models["VaultSyncOutput"]
VaultCheckOutput: type[BaseModel] = _models["VaultCheckOutput"]
VaultLinksOutput: type[BaseModel] = _models["VaultLinksOutput"]


def load_vault(cfg: dict[str, Any] | None = None) -> _AbstractVault:
    """Build the configured vault implementation."""
    if cfg is None:
        from ..config.WKSConfig import WKSConfig

        cfg = WKSConfig.load().to_dict()

    vault_cfg = cfg.get("vault", {})
    vault_type = (vault_cfg.get("type") or "obsidian").lower()

    if vault_type != "obsidian":
        raise SystemExit(f"Fatal: unsupported vault.type '{vault_type}'")

    base_path = vault_cfg.get("base_dir")
    if not base_path:
        raise SystemExit("Fatal: 'vault.base_dir' is required in config")

    return ObsidianVault(vault_path=Path(expand_path(base_path)))


__all__ = [
    "ObsidianVault",
    "VaultCheckOutput",
    "VaultLinksOutput",
    "VaultStatusOutput",
    "VaultSyncOutput",
    "load_vault",
]
