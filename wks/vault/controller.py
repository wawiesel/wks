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

        Returns:
            (set of (rel_path, symlink_path), notes_scanned)
        """
        links_to_create: Set[Tuple[str, Path]] = set()
        notes_scanned = 0

        for note_path in self.vault.iter_markdown_files():
            notes_scanned += 1
            try:
                text = note_path.read_text(encoding="utf-8")
                for link in parse_wikilinks(text):
                    target = link.target
                    if target.startswith("_links/"):
                        # Extract relative path after _links/
                        rel_path = target[len("_links/"):]
                        symlink_path = self.vault.links_dir / rel_path

                        if not symlink_path.exists():
                            links_to_create.add((rel_path, symlink_path))
            except Exception:
                continue

        return links_to_create, notes_scanned

    def _infer_target_path(self, rel_path: str) -> Optional[Path]:
        """Infer filesystem target path from _links/ relative path.

        Args:
            rel_path: Relative path like "machine/path/to/file" or "Pictures/file.png"

        Returns:
            Absolute target path or None if cannot infer
        """
        parts = Path(rel_path).parts
        if len(parts) == 0:
            return None

        # Try machine-prefixed path first
        if parts[0] == self.machine:
            # This is a machine-specific link: _links/machine/path/to/file
            return Path("/") / Path(*parts[1:])

        # Try as Pictures/ or Documents/ relative path
        if parts[0] in ["Pictures", "Documents", "Downloads", "Desktop"]:
            # _links/Pictures/file.png → ~/Pictures/file.png
            return Path.home() / Path(*parts)

        # Unknown format
        return None

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
