"""Vault integration entry points."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# from ..config import load_config
from ..constants import WKS_HOME_DISPLAY
from ..utils import expand_path
from .controller import VaultController
from .obsidian import ObsidianVault

VaultType = ObsidianVault  # Future types can extend Protocols/ABC

_VAULT_CLASSES: dict[str, type[ObsidianVault]] = {
    "obsidian": ObsidianVault,
}


def _resolve_obsidian_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    """Extract the minimal Obsidian settings required for vault mode."""
    vault_cfg = cfg.get("vault", {}) or {}
    base_path = vault_cfg.get("base_dir")
    if not base_path:
        raise SystemExit(f"Fatal: 'vault.base_dir' is required in {WKS_HOME_DISPLAY}/config.json")
    wks_dir = vault_cfg.get("wks_dir")
    if not wks_dir:
        raise SystemExit(f"Fatal: 'vault.wks_dir' is required in {WKS_HOME_DISPLAY}/config.json")
    return {
        "vault_path": expand_path(base_path),
        "base_dir": wks_dir,
    }


def load_vault(cfg: dict[str, Any] | None = None) -> ObsidianVault:
    """Build the configured vault implementation."""
    if cfg is None:
        from ..config import load_config

        cfg = load_config()
    # cfg = cfg or load_config()
    vault_cfg = cfg.get("vault", {})
    vault_type = (vault_cfg.get("type") or "obsidian").lower()
    if vault_type not in _VAULT_CLASSES:
        raise SystemExit(f"Fatal: unsupported vault.type '{vault_type}'")
    if vault_type == "obsidian":
        settings = _resolve_obsidian_settings(cfg)
        return ObsidianVault(
            vault_path=Path(settings["vault_path"]),
            base_dir=settings["base_dir"],
        )
    raise SystemExit(f"Fatal: unsupported vault.type '{vault_type}'")


__all__ = ["ObsidianVault", "VaultController", "load_vault"]
