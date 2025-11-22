"""Vault Controller - Business logic for vault operations."""

from __future__ import annotations

__all__ = ["VaultController"]

from typing import Any, Dict

from .config import VaultDatabaseConfig
from .indexer import VaultLinkIndexer
from .obsidian import ObsidianVault
from .status_controller import VaultStatusController


class VaultController:
    """Controller for vault operations - returns data structures for any view."""

    @staticmethod
    def get_status(config: Dict[str, Any]) -> Dict[str, Any]:
        """Get vault link status summary.

        Args:
            config: Configuration dictionary

        Returns:
            dict with vault status including link counts, issues, and errors

        Raises:
            VaultConfigError: If vault configuration is invalid
        """
        controller = VaultStatusController(cfg=config)
        summary = controller.summarize()
        return summary.to_dict()

    @staticmethod
    def sync_vault(config: Dict[str, Any], batch_size: int = 1000) -> Dict[str, Any]:
        """Sync vault links to MongoDB.

        Args:
            config: Configuration dictionary
            batch_size: Number of records to process per batch (default 1000)

        Returns:
            dict with sync statistics (notes scanned, edges written, duration, etc.)

        Raises:
            VaultConfigError: If vault configuration is invalid
        """
        from .obsidian import ObsidianVault
        from ..vault import load_vault

        vault = load_vault(config)
        indexer = VaultLinkIndexer.from_config(vault, cfg=config)
        result = indexer.sync(batch_size=batch_size)

        return {
            "sync_started": result.sync_started,
            "sync_duration_ms": result.sync_duration_ms,
            "notes_scanned": result.stats.notes_scanned,
            "edges_written": result.stats.edge_total,
            "type_counts": result.stats.type_counts,
            "status_counts": result.stats.status_counts,
            "deleted_records": result.deleted_records,
            "upserts": result.upserts,
            "errors": result.stats.errors,
        }
