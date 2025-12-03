"""Vault controller with business logic for vault operations."""

import platform
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .obsidian import ObsidianVault


@dataclass
class SymlinkFixResult:
    """Result from fix_symlinks operation."""

    notes_scanned: int
    links_found: int
    created: int
    failed: List[Tuple[str, str]]  # (rel_path, reason)


class VaultController:
    """Business logic for vault operations."""

    def __init__(self, vault: ObsidianVault, machine_name: Optional[str] = None):
        """Initialize vault controller.

        Args:
            vault: ObsidianVault instance
            machine_name: Machine name for symlink paths (defaults to platform.node())
        """
        self.vault = vault
        self.machine = machine_name or platform.node().split(".")[0]

    def fix_symlinks(self) -> SymlinkFixResult:
        """Rebuild _links/<machine>/ from vault DB.

        Deletes entire _links/<machine>/ directory and recreates all symlinks
        based on vault DB records where to_uri starts with file://.

        Returns:
            SymlinkFixResult with operation statistics
        """
        import shutil

        from pymongo import MongoClient

        from ..config import WKSConfig

        # 1. Delete entire _links/<machine>/ directory
        machine_links_dir = self.vault.links_dir / self.machine
        if machine_links_dir.exists():
            try:
                shutil.rmtree(machine_links_dir)
            except Exception as exc:
                return SymlinkFixResult(
                    notes_scanned=0,
                    links_found=0,
                    created=0,
                    failed=[("_links/" + self.machine, f"Failed to delete: {exc}")],
                )

        # 2. Query vault DB for all file:// links
        try:
            config = WKSConfig.load()
            mongo_uri = config.mongo.uri
            db_name = config.vault.database.split(".")[0]
            coll_name = config.vault.database.split(".")[1]
        except Exception as e:
            return SymlinkFixResult(
                notes_scanned=0,
                links_found=0,
                created=0,
                failed=[("config", f"Failed to load config: {e}")],
            )

        try:
            client = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,
                retryWrites=True,
                retryReads=True,
            )
            collection = client[db_name][coll_name]

            # Find all links where to_uri is file://
            cursor = collection.find({"to_uri": {"$regex": "^file://"}}, {"to_uri": 1})

            file_uris = set(doc["to_uri"] for doc in cursor)
            client.close()

        except Exception as exc:
            return SymlinkFixResult(
                notes_scanned=0,
                links_found=0,
                created=0,
                failed=[("vault_db", f"Failed to query: {exc}")],
            )

        # 3. Create symlinks for each unique file:// URI
        created = 0
        failed: List[Tuple[str, str]] = []

        for file_uri in sorted(file_uris):
            if not file_uri.startswith("file://"):
                continue

            # Parse file:// URI to filesystem path
            from urllib.parse import urlparse

            parsed = urlparse(file_uri)
            target_path = Path(parsed.path)

            if not target_path.exists():
                failed.append((file_uri, "Target file not found"))
                continue

            # Build symlink path: _links/<machine>/path/to/file
            try:
                relative = target_path.resolve().relative_to(Path("/"))
                symlink_path = self.vault.links_dir / self.machine / relative
            except Exception as exc:
                failed.append((file_uri, f"Cannot create relative path: {exc}"))
                continue

            # Create symlink
            try:
                symlink_path.parent.mkdir(parents=True, exist_ok=True)
                symlink_path.symlink_to(target_path)
                created += 1
            except Exception as exc:
                failed.append((str(symlink_path), f"Failed to create symlink: {exc}"))

        return SymlinkFixResult(
            notes_scanned=0,  # We queried DB, not markdown files
            links_found=len(file_uris),
            created=created,
            failed=failed,
        )

    def validate_vault(self) -> dict:
        """Validate all vault links (check for broken links).

        Returns:
            Dictionary with validation results
        """
        from .indexer import VaultLinkScanner

        scanner = VaultLinkScanner(self.vault)
        records = scanner.scan()
        stats = scanner.stats

        broken_links = [r for r in records if r.status != "ok"]
        broken_by_status = {}
        for record in broken_links:
            broken_by_status.setdefault(record.status, []).append(
                {
                    "note_path": str(record.note_path),
                    "line_number": record.line_number,
                    "raw_target": record.raw_target,
                    "status": record.status,
                }
            )

        return {
            "notes_scanned": stats.notes_scanned,
            "links_found": stats.edge_total,
            "broken_count": len(broken_links),
            "broken_by_status": broken_by_status,
            "is_valid": len(broken_links) == 0,
        }

    # ------------------------------------------------------------------ sync helper
    @staticmethod
    def sync_vault(cfg: Optional[dict] = None, batch_size: int = 1000, incremental: bool = False) -> dict:
        """Sync vault links to MongoDB (wrapper for CLI/MCP)."""
        from ..config import WKSConfig
        from ..utils import expand_path
        from .indexer import VaultLinkIndexer

        config = WKSConfig.load()
        base_dir = config.vault.base_dir
        wks_dir = config.vault.wks_dir
        if not base_dir:
            raise ValueError("vault.base_dir not configured")

        vault = ObsidianVault(expand_path(base_dir), base_dir=wks_dir)
        indexer = VaultLinkIndexer.from_config(vault, config)
        result = indexer.sync(batch_size=batch_size, incremental=incremental)

        return {
            "notes_scanned": result.stats.notes_scanned,
            "edges_written": result.stats.edge_total,
            "sync_duration_ms": result.sync_duration_ms,
            "errors": result.stats.errors,
        }
