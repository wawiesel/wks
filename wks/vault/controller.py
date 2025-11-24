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

    def _collect_missing_links(self) -> Tuple[Set[Tuple[str, Path]], int]:
        """Scan vault and collect missing _links/ references.

        Ensures every link is normalized to include the machine prefix by
        rewriting notes in-place when necessary.

        Returns:
            (set of (rel_path, symlink_path), notes_scanned)
        """
        links_to_create: Set[Tuple[str, Path]] = set()
        notes_scanned = 0

        for note_path in self.vault.iter_markdown_files():
            notes_scanned += 1
            try:
                text = note_path.read_text(encoding="utf-8")
            except Exception:
                continue

            lines = text.splitlines()
            updated = False

            for link in parse_wikilinks(text):
                target = link.target
                if not target.startswith("_links/"):
                    continue

                rel_path = target[len("_links/"):]
                normalized_rel = rel_path.lstrip("/")

                # Always prefix with this machine name
                if not normalized_rel.startswith(f"{self.machine}/"):
                    normalized_rel = f"{self.machine}/{normalized_rel}"

                remainder = Path(*Path(normalized_rel).parts[1:])
                root_like = {"Users", "private", "var", "tmp"}
                if remainder.parts and remainder.parts[0] not in root_like:
                    home_rel = Path.home().relative_to(Path("/"))
                    remainder = home_rel / remainder
                    normalized_rel = f"{self.machine}/{remainder.as_posix()}"

                # Rebuild the wikilink target (preserve alias) if changed
                desired_target = f"_links/{normalized_rel}"
                new_inner = desired_target
                if link.alias:
                    new_inner = f"{new_inner}|{link.alias}"

                old_markup = f"{'!' if link.is_embed else ''}[[{link.raw_target}]]"
                new_markup = f"{'!' if link.is_embed else ''}[[{new_inner}]]"
                if old_markup != new_markup:
                    line_idx = link.line_number - 1
                    if 0 <= line_idx < len(lines):
                        if old_markup in lines[line_idx]:
                            lines[line_idx] = lines[line_idx].replace(old_markup, new_markup)
                        else:
                            # Fallback: replace inner target if markup shape differed
                            lines[line_idx] = lines[line_idx].replace(link.raw_target, new_inner)
                        updated = True

                symlink_path = self.vault.links_dir / normalized_rel

                if not symlink_path.exists():
                    links_to_create.add((normalized_rel, symlink_path))

            if updated:
                try:
                    note_path.write_text("\n".join(lines), encoding="utf-8")
                except Exception:
                    # Best effort; continue processing other files
                    pass

        return links_to_create, notes_scanned

    def _infer_target_path(self, rel_path: str) -> Optional[Path]:
        """Infer filesystem target path from _links/ relative path.

        Args:
            rel_path: Relative path like "machine/path/to/file"

        Returns:
            Absolute target path or None if cannot infer
        """
        parts = Path(rel_path).parts
        if len(parts) < 2:
            return None

        if parts[0] != self.machine:
            return None

        remainder = Path(*parts[1:])

        root_like = {"Users", "private", "var", "tmp"}
        if remainder.parts and remainder.parts[0] not in root_like:
            home_rel = Path.home().relative_to(Path("/"))
            remainder = home_rel / remainder

        return Path("/") / remainder

    def _create_symlink(self, rel_path: str, symlink_path: Path, target_path: Path) -> Tuple[bool, Optional[str]]:
        """Create symlink to target.

        Args:
            rel_path: Relative path for error reporting
            symlink_path: Symlink path to create
            target_path: Target path to link to

        Returns:
            (success: bool, error_msg: Optional[str])
        """
        if not target_path.exists():
            return False, f"Target not found: {target_path}"

        try:
            symlink_path.parent.mkdir(parents=True, exist_ok=True)
            symlink_path.symlink_to(target_path)
            return True, None
        except Exception as exc:
            return False, str(exc)

    def fix_symlinks(self) -> SymlinkFixResult:
        """Find and create missing _links/ symlinks.

        Returns:
            SymlinkFixResult with operation statistics
        """
        # 1. Collect missing links
        links_to_create, notes_scanned = self._collect_missing_links()

        if not links_to_create:
            return SymlinkFixResult(
                notes_scanned=notes_scanned,
                links_found=0,
                created=0,
                failed=[]
            )

        # 2. Create symlinks
        created = 0
        failed: List[Tuple[str, str]] = []

        for rel_path, symlink_path in sorted(links_to_create):
            # Infer target path
            target_path = self._infer_target_path(rel_path)
            if target_path is None:
                failed.append((rel_path, "Unknown path format"))
                continue

            # Create symlink
            success, error = self._create_symlink(rel_path, symlink_path, target_path)
            if success:
                created += 1
            else:
                failed.append((rel_path, error))

        return SymlinkFixResult(
            notes_scanned=notes_scanned,
            links_found=len(links_to_create),
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
