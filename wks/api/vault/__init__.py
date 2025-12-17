"""Vault integration entry points."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...utils import expand_path

# from ..config import load_config
from ...utils.constants import WKS_HOME_DISPLAY
from ._AbstractVault import _AbstractVault
from .controller import VaultController
from .obsidian import ObsidianVault

VaultType = _AbstractVault

_VAULT_CLASSES: dict[str, type[_AbstractVault]] = {
    "obsidian": ObsidianVault,
}


def _resolve_obsidian_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    """Extract the minimal Obsidian settings required for vault mode."""
    vault_cfg = cfg.get("vault", {}) or {}
    base_path = vault_cfg.get("base_dir")
    if not base_path:
        raise SystemExit(f"Fatal: 'vault.base_dir' is required in {WKS_HOME_DISPLAY}/config.json")
    return {
        "vault_path": expand_path(base_path),
    }


def load_vault(cfg: dict[str, Any] | None = None) -> _AbstractVault:
    """Build the configured vault implementation."""
    if cfg is None:
        from ..config.WKSConfig import WKSConfig

        cfg = WKSConfig.load().to_dict()
    # cfg = cfg or load_config()
    vault_cfg = cfg.get("vault", {})
    vault_type = (vault_cfg.get("type") or "obsidian").lower()
    if vault_type not in _VAULT_CLASSES:
        raise SystemExit(f"Fatal: unsupported vault.type '{vault_type}'")
    if vault_type == "obsidian":
        settings = _resolve_obsidian_settings(cfg)
        return ObsidianVault(
            vault_path=Path(settings["vault_path"]),
        )
    raise SystemExit(f"Fatal: unsupported vault.type '{vault_type}'")


__all__ = ["ObsidianVault", "VaultController", "load_vault"]
