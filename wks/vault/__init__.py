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
    """Extract Obsidian-specific settings from the vault section only."""
    vault_cfg = cfg.get("vault", {}) or {}
    base_path = vault_cfg.get("base_dir")
    if not base_path:
        raise SystemExit(
            f"Fatal: 'vault.base_dir' is required in {WKS_HOME_DISPLAY}/config.json"
        )
    wks_dir = vault_cfg.get("wks_dir")
    if not wks_dir:
        raise SystemExit(
            f"Fatal: 'vault.wks_dir' is required in {WKS_HOME_DISPLAY}/config.json"
        )

    numeric_fields = [
        "log_max_entries",
        "active_files_max_rows",
        "source_max_chars",
        "destination_max_chars",
    ]
    missing = [f"vault.{key}" for key in numeric_fields if key not in vault_cfg]
    if missing:
        raise SystemExit(
            f"Fatal: missing required config key(s): {', '.join(missing)} "
            f"in {WKS_HOME_DISPLAY}/config.json"
        )

    def _coerce_positive_int(key: str) -> int:
        value = vault_cfg[key]
        try:
            result = int(value)
        except (TypeError, ValueError):
            raise SystemExit(
                f"Fatal: vault.{key} must be an integer (found: {value!r}) "
                f"in {WKS_HOME_DISPLAY}/config.json"
            ) from None
        if result < 1:
            raise SystemExit(
                f"Fatal: vault.{key} must be >= 1 (found: {result}) "
                f"in {WKS_HOME_DISPLAY}/config.json"
            )
        return result

    return {
        "vault_path": expand_path(base_path),
        "base_dir": wks_dir,
        "log_max_entries": _coerce_positive_int("log_max_entries"),
        "active_files_max_rows": _coerce_positive_int("active_files_max_rows"),
        "source_max_chars": _coerce_positive_int("source_max_chars"),
        "destination_max_chars": _coerce_positive_int("destination_max_chars"),
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
