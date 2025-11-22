"""Vault configuration management."""

from __future__ import annotations

__all__ = ["VaultConfigError", "VaultDatabaseConfig"]

from dataclasses import dataclass
from typing import Any, Dict

from ..db_helpers import parse_database_key


class VaultConfigError(Exception):
    """Raised when vault configuration is invalid."""


@dataclass
class VaultDatabaseConfig:
    """MongoDB configuration for vault link storage."""

    mongo_uri: str
    db_name: str
    coll_name: str

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "VaultDatabaseConfig":
        """Extract and validate vault database configuration.

        Args:
            cfg: Full WKS configuration dictionary

        Returns:
            VaultDatabaseConfig instance

        Raises:
            VaultConfigError: If required configuration is missing or invalid
        """
        db_cfg = cfg.get("db")
        if not db_cfg or not db_cfg.get("uri"):
            raise VaultConfigError(
                "db.uri is required in config "
                "(found: missing, expected: MongoDB connection URI string)"
            )

        vault_cfg = cfg.get("vault")
        if not vault_cfg or not vault_cfg.get("database"):
            raise VaultConfigError(
                "vault.database is required in config "
                "(found: missing, expected: 'database.collection' value)"
            )

        try:
            db_name, coll_name = parse_database_key(vault_cfg["database"])
        except (ValueError, KeyError) as exc:
            raise VaultConfigError(
                f"vault.database format invalid: {exc}"
            ) from exc

        return cls(
            mongo_uri=db_cfg["uri"],
            db_name=db_name,
            coll_name=coll_name,
        )
