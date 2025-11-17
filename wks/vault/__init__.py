"""Vault integration entry points."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Type

from ..config import load_config
from ..constants import WKS_HOME_DISPLAY
from ..utils import expand_path
from .obsidian import ObsidianVault

VaultType = ObsidianVault  # Future types can extend Protocols/ABC

_VAULT_CLASSES: Dict[str, Type[ObsidianVault]] = {
    "obsidian": ObsidianVault,
}


def _resolve_obsidian_settings(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Obsidian-specific settings with backward-compatible keys."""
    vault_cfg = cfg.get("vault", {})
    obs_cfg = cfg.get("obsidian", {})
    base_path = vault_cfg.get("base_dir") or cfg.get("vault_path")
    if not base_path:
        raise SystemExit(
            f"Fatal: 'vault.base_dir' is required (or legacy 'vault_path') in {WKS_HOME_DISPLAY}/config.json"
        )
    wks_dir = vault_cfg.get("wks_dir") or obs_cfg.get("base_dir") or "WKS"
    settings = {
        "vault_path": base_path,
        "base_dir": wks_dir,
        "log_max_entries": obs_cfg.get("log_max_entries"),
        "active_files_max_rows": obs_cfg.get("active_files_max_rows"),
        "source_max_chars": obs_cfg.get("source_max_chars"),
        "destination_max_chars": obs_cfg.get("destination_max_chars"),
    }
    missing = [
        key for key, value in settings.items()
        if key not in {"vault_path", "base_dir"} and value is None
    ]
    if missing:
        missing_fmt = ", ".join(f"obsidian.{m}" for m in missing)
        raise SystemExit(
            f"Fatal: missing required config key(s): {missing_fmt} "
            f"in {WKS_HOME_DISPLAY}/config.json"
        )
    return {
        "vault_path": expand_path(settings["vault_path"]),
        "base_dir": settings["base_dir"],
        "log_max_entries": int(settings["log_max_entries"]),
        "active_files_max_rows": int(settings["active_files_max_rows"]),
        "source_max_chars": int(settings["source_max_chars"]),
        "destination_max_chars": int(settings["destination_max_chars"]),
    }


def load_vault(cfg: Optional[Dict[str, Any]] = None) -> ObsidianVault:
    """Build the configured vault implementation."""
    cfg = cfg or load_config()
    vault_cfg = cfg.get("vault", {})
    vault_type = (vault_cfg.get("type") or "obsidian").lower()
    if vault_type not in _VAULT_CLASSES:
        raise SystemExit(f"Fatal: unsupported vault.type '{vault_type}'")
    if vault_type == "obsidian":
        settings = _resolve_obsidian_settings(cfg)
        return ObsidianVault(
            vault_path=Path(settings["vault_path"]),
            base_dir=settings["base_dir"],
            log_max_entries=settings["log_max_entries"],
            active_files_max_rows=settings["active_files_max_rows"],
            source_max_chars=settings["source_max_chars"],
            destination_max_chars=settings["destination_max_chars"],
        )
    raise SystemExit(f"Fatal: unsupported vault.type '{vault_type}'")


__all__ = ["ObsidianVault", "load_vault"]
