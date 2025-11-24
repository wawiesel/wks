"""Vault controller with business logic for vault operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Set, Tuple, Optional
import platform

from .obsidian import ObsidianVault
from .markdown_parser import parse_wikilinks


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
        from pymongo import MongoClient
        from ..config import load_config
        from .config import VaultDatabaseConfig
        import shutil

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
                    failed=[("_links/" + self.machine, f"Failed to delete: {exc}")]
                )

        # 2. Query vault DB for all file:// links
        cfg = load_config()
        db_config = VaultDatabaseConfig.from_config(cfg)

        try:
            client = MongoClient(
                db_config.mongo_uri,
                serverSelectionTimeoutMS=5000,
                retryWrites=True,
                retryReads=True,
            )
            collection = client[db_config.db_name][db_config.coll_name]

            # Find all links where to_uri is file://
            cursor = collection.find(
                {"to_uri": {"$regex": "^file://"}},
                {"to_uri": 1}
            )

            file_uris = set(doc["to_uri"] for doc in cursor)
            client.close()

        except Exception as exc:
            return SymlinkFixResult(
                notes_scanned=0,
                links_found=0,
                created=0,
                failed=[("vault_db", f"Failed to query: {exc}")]
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
            failed=failed
        )

    # ------------------------------------------------------------------ sync helper
    @staticmethod
    def sync_vault(cfg: Optional[dict] = None, batch_size: int = 1000, incremental: bool = False) -> dict:
        """Sync vault links to MongoDB (wrapper for CLI/MCP)."""
        from ..config import load_config
        from ..utils import expand_path
        from .indexer import VaultLinkIndexer

        cfg = cfg or load_config()
        vault_cfg = cfg.get("vault", {}) or {}
        base_dir = vault_cfg.get("base_dir")
        wks_dir = vault_cfg.get("wks_dir", "WKS")
        if not base_dir:
            raise ValueError("vault.base_dir not configured")

        vault = ObsidianVault(expand_path(base_dir), base_dir=wks_dir)
        indexer = VaultLinkIndexer.from_config(vault, cfg)
        result = indexer.sync(batch_size=batch_size, incremental=incremental)

        return {
            "notes_scanned": result.stats.notes_scanned,
            "edges_written": result.stats.edge_total,
            "sync_duration_ms": result.sync_duration_ms,
            "errors": result.stats.errors,
        }
