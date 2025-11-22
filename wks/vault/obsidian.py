"""
Lean Obsidian vault integration for WKS.

Only the pieces required for link maintenance remain; legacy log/health
tables are intentionally disabled until those features are needed again.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import load_config, timestamp_format, DEFAULT_TIMESTAMP_FORMAT


class ObsidianVault:
    """Minimal interface to an Obsidian vault for link maintenance."""

    def __init__(self, vault_path: Path, *, base_dir: str):
        self.vault_path = Path(vault_path)
        if not base_dir or not str(base_dir).strip():
            raise ValueError("vault.wks_dir is required in configuration")
        self.base_dir = str(base_dir).strip("/")
        self._recompute_paths()
        try:
            cfg = load_config()
            self.timestamp_format = timestamp_format(cfg)
        except Exception:
            self.timestamp_format = DEFAULT_TIMESTAMP_FORMAT

    # ------------------------------------------------------------------ helpers

    def _base_path(self) -> Path:
        return self.vault_path / self.base_dir

    def _recompute_paths(self) -> None:
        base = self._base_path()
        self.links_dir = self.vault_path / "_links"
        self.projects_dir = self.vault_path / "Projects"
        self.people_dir = self.vault_path / "People"
        self.topics_dir = self.vault_path / "Topics"
        self.ideas_dir = self.vault_path / "Ideas"
        self.orgs_dir = self.vault_path / "Organizations"
        self.records_dir = self.vault_path / "Records"
        self.docs_dir = base / "Docs"

    def set_base_dir(self, base_dir: str) -> None:
        self.base_dir = base_dir.strip("/")
        self._recompute_paths()

    def ensure_structure(self) -> None:
        """Create the base directories that the daemon expects."""
        self._base_path().mkdir(parents=True, exist_ok=True)
        for directory in [
            self.links_dir,
            self.projects_dir,
            self.people_dir,
            self.topics_dir,
            self.ideas_dir,
            self.orgs_dir,
            self.records_dir,
            self.docs_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- link ops

    def _link_rel_for_source(self, source_file: Path, preserve_structure: bool = True) -> str:
        if preserve_structure:
            home = Path.home()
            try:
                relative = source_file.resolve().relative_to(home)
                return f"_links/{relative.as_posix()}"
            except Exception:
                return f"_links/{source_file.name}"
        return f"_links/{source_file.name}"

    def link_file(self, source_file: Path, preserve_structure: bool = True) -> Optional[Path]:
        if not source_file.exists():
            return None

        if preserve_structure:
            home = Path.home()
            try:
                relative = source_file.resolve().relative_to(home)
                link_path = self.links_dir / relative
            except ValueError:
                link_path = self.links_dir / source_file.name
        else:
            link_path = self.links_dir / source_file.name

        link_path.parent.mkdir(parents=True, exist_ok=True)
        if not link_path.exists():
            link_path.symlink_to(source_file)
        return link_path

    def update_link_on_move(self, old_path: Path, new_path: Path) -> None:
        home = Path.home()
        try:
            relative_old = old_path.resolve().relative_to(home)
        except (ValueError, OSError):
            # Path not relative to home or resolution failed
            return
        old_link = self.links_dir / relative_old
        if old_link.exists() and old_link.is_symlink():
            try:
                old_link.unlink()
            except (OSError, PermissionError):
                # Cannot remove old link
                return
            self.link_file(new_path)

    def _iter_vault_markdown(self):
        for md in self.vault_path.rglob("*.md"):
            # Skip root-level _links/ directory (symlinked external files)
            try:
                rel_to_vault = md.relative_to(self.vault_path)
                if rel_to_vault.parts[0] == "_links":
                    continue
            except (ValueError, IndexError):
                # Path not relative to vault or no parts
                continue
            # Skip .wks/ directories (MongoDB internal data)
            if ".wks" in md.parts:
                continue
            try:
                yield md
            except (OSError, PermissionError):
                # Skip files we don't have permission to access
                continue

    def iter_markdown_files(self):
        """Public iterator (used by the indexer)."""
        yield from self._iter_vault_markdown()

    def update_vault_links_on_move(self, old_path: Path, new_path: Path) -> None:
        old_rel = self._link_rel_for_source(old_path)
        new_rel = self._link_rel_for_source(new_path)
        if old_rel == new_rel:
            return
        old_rel_legacy = old_rel.replace("_links/", "links/")
        new_rel_legacy = new_rel.replace("_links/", "links/")
        patterns = [
            (f"[[{old_rel}]]", f"[[{new_rel}]]"),
            (f"[[{old_rel}|", f"[[{new_rel}|"),
            (f"`{old_rel}`", f"`{new_rel}`"),
            (f"[[{old_rel_legacy}]]", f"[[{new_rel}]]"),
            (f"[[{old_rel_legacy}|", f"[[{new_rel}|"),
            (f"`{old_rel_legacy}`", f"`{new_rel}`"),
        ]
        for md in self._iter_vault_markdown():
            try:
                content = md.read_text(encoding="utf-8")
            except (IOError, OSError, UnicodeDecodeError, PermissionError):
                continue
            original = content
            for a, b in patterns:
                content = content.replace(a, b)
            if content != original:
                try:
                    md.write_text(content, encoding="utf-8")
                except (IOError, OSError, PermissionError):
                    pass

    def mark_reference_deleted(self, path: Path) -> None:
        rel = self._link_rel_for_source(path)
        marker = f"🗑️ deleted: [[{rel}]]"
        legacy = rel.replace("_links/", "links/")
        for md in self._iter_vault_markdown():
            try:
                content = md.read_text(encoding="utf-8")
            except (IOError, OSError, UnicodeDecodeError, PermissionError):
                continue
            if marker in content or legacy in content:
                continue
            lines = content.splitlines()
            lines.insert(1, f"> {marker}")
            try:
                md.write_text("\n".join(lines), encoding="utf-8")
            except (IOError, OSError, PermissionError):
                pass

    # ---------------------------------------------------------------- no-op stubs

    def log_file_operation(self, *args, **kwargs) -> None:  # pragma: no cover - disabled
        return

    def update_active_files(self, *args, **kwargs) -> None:  # pragma: no cover - disabled
        return

    def write_health_page(self) -> None:  # pragma: no cover - disabled
        return

    # ---------------------------------------------------------------- misc helpers

    def _format_dt(self, dt: datetime) -> str:
        try:
            return dt.strftime(self.timestamp_format)
        except (ValueError, TypeError):
            # Invalid format string or datetime
            return dt.strftime(DEFAULT_TIMESTAMP_FORMAT)

    def write_doc_text(self, content_hash: str, source_path: Path, text: str, keep: int = 99):
        docs_dir = self.docs_dir
        docs_dir.mkdir(parents=True, exist_ok=True)
        doc_path = docs_dir / f"{content_hash}.md"
        header = (
            f"# {source_path.name}\n\n"
            f"`{source_path}`\n\n"
            f"*Checksum:* `{content_hash}`  *Updated:* {self._format_dt(datetime.now())}\n\n"
            "---\n\n"
        )
        try:
            doc_path.write_text(header + text, encoding="utf-8")
        except (IOError, OSError, PermissionError):
            return
        try:
            entries = sorted(docs_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in entries[keep:]:
                try:
                    old.unlink()
                except (OSError, PermissionError):
                    pass
        except (OSError, PermissionError):
            pass

    def create_project_note(self, project_path: Path, status: str = "Active", description: Optional[str] = None) -> Path:
        project_name = project_path.name
        note_path = self.projects_dir / f"{project_name}.md"
        parts = project_name.split("-", 1)
        name = parts[1] if len(parts) > 1 else project_name
        content = f"""# {project_name}

**Status:** {status}
**Created:** {datetime.now().strftime('%Y-%m-%d')}
**Location:** `{project_path}`

## Overview

{description or f"Project: {name}"}

## Links

- Project directory: [[_links/{project_name}]]
- Related topics:

## Notes

"""
        note_path.write_text(content)
        return note_path

    def link_project(self, project_path: Path) -> list[Path]:
        links_created = []
        for filename in ["README.md", "SPEC.md", "TODO.md", "NOTES.md"]:
            file_path = project_path / filename
            if file_path.exists():
                link = self.link_file(file_path)
                if link:
                    links_created.append(link)
        return links_created

    def find_broken_links(self) -> list[Path]:
        broken = []
        for link in self.links_dir.rglob("*"):
            if link.is_symlink() and not link.exists():
                broken.append(link)
        return broken

    def cleanup_broken_links(self) -> int:
        broken = self.find_broken_links()
        for link in broken:
            try:
                link.unlink()
            except (OSError, PermissionError):
                pass
        return len(broken)
