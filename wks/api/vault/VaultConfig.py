"""Vault configuration management."""

from __future__ import annotations

__all__ = ["VaultConfig"]

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class VaultConfig(BaseModel):
    """Vault configuration model."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., description="Vault backend type")
    base_dir: str = Field(..., description="Path to vault root directory")

    @field_validator("base_dir")
    @classmethod
    def _normalize_base_dir(cls, v: str) -> str:
        from wks.api.config.normalize_path import normalize_path

        return str(normalize_path(v))

    @classmethod
    def from_config_dict(cls, config: dict[str, Any]) -> VaultConfig:
        """Load vault config from config dict."""
        vault_config = config.get("vault")
        if not vault_config:
            # We raise ValueError to match existing patterns (or KeyError in MonitorConfig?)
            # MonitorConfig raises KeyError but checks explicitly.
            # WKSConfig raises ValueError.
            raise ValueError("vault section is required in config")

        try:
            return cls(**vault_config)
        except ValidationError as e:
            # Re-raise or let it bubble? WKSConfig catches ValidationError.
            # But if called directly, we might want it to bubble.
            raise e


_BACKEND_REGISTRY = {
    "obsidian": "wks.api.vault._obsidian",
}
