"""
Obsidian vault integration for WKS.

Simple, single-file logs under a required base_dir (default: "WKS").
"""

import hashlib
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime


class ObsidianVault:
    """Interface to an Obsidian vault for WKS."""

    def __init__(self, vault_path: Path, *, base_dir: str, log_max_entries: int, active_files_max_rows: int, source_max_chars: int, destination_max_chars: int):
        """
        Initialize vault interface.

        Args:
            vault_path: Path to Obsidian vault (e.g., ~/obsidian)
        """
        self.vault_path = Path(vault_path)
        # Required base directory under the vault for WKS-managed logs and docs
        if not base_dir or not str(base_dir).strip():
            raise ValueError("obsidian.base_dir is required in configuration")
        self.base_dir = str(base_dir).strip("/")
        self._recompute_paths()
        # File log paths (single-file mode)
        self.file_log_path = self._base_path() / "FileOperations.md"
        self.activity_log_path = self._base_path() / "ActiveFiles.md"
        self.log_max_entries = int(log_max_entries)
        self.active_files_max_rows = int(active_files_max_rows)
        # Table width controls for path columns
        self.source_max_chars = int(source_max_chars)
        self.destination_max_chars = int(destination_max_chars)
        # Append-only JSONL ledger for file operations used to rebuild the log
        self.ops_ledger_path = Path.home() / ".wks" / "file_ops.jsonl"
        self.ops_ledger_max_lines = 20000
        self.ops_ledger_keep_lines = 10000
        # Throttle for markdown rewrites (seconds)
        self._write_throttle_secs = 2.0
        self._last_ops_write_ts = 0.0
        self._last_active_write_ts = 0.0
        # Health page throttle
        self._last_health_write_ts = 0.0
        try:
            self.ops_ledger_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.ops_ledger_path.exists():
                self.ops_ledger_path.write_text("")
        except Exception:
            pass

    def _shorten_path(self, p: Path, max_chars: int) -> str:
        """Return a compact string for a path, using ~ for home and mid-ellipsis if too long."""
        try:
            rel = p.relative_to(Path.home())
            s = f"~/{rel}"
        except ValueError:
            s = str(p)
        if len(s) <= max_chars:
            return s
        if max_chars <= 3:
            return s[-max_chars:]
        head = max_chars // 2 - 1
        tail = max_chars - head - 1
        return s[:head] + "…" + s[-tail:]

    def _base_path(self) -> Path:
        return self.vault_path / self.base_dir

    def _recompute_paths(self):
        # Category folders always live at vault root
        # Use internal _links directory for embedded content management
        self.links_dir = self.vault_path / "_links"
        self.projects_dir = self.vault_path / "Projects"
        self.people_dir = self.vault_path / "People"
        self.topics_dir = self.vault_path / "Topics"
        self.ideas_dir = self.vault_path / "Ideas"
        self.orgs_dir = self.vault_path / "Organizations"
        self.records_dir = self.vault_path / "Records"

    def set_base_dir(self, base_dir: str):
        """Set the base subdirectory under the vault for WKS-managed content."""
        self.base_dir = base_dir.strip("/")
        self._recompute_paths()
        self.file_log_path = self._base_path() / "FileOperations.md"
        self.activity_log_path = self._base_path() / "ActiveFiles.md"

    def _get_file_log_path(self) -> Path:
        return self.file_log_path

    def _append_ops_ledger(self, record: dict):
        """Append a JSON line record to the operations ledger."""
        try:
            import json as _json
            with open(self.ops_ledger_path, 'a', encoding='utf-8') as f:
                f.write(_json.dumps(record, ensure_ascii=False) + "\n")
            # Compact/rotate if too large
            try:
                lines = self.ops_ledger_path.read_text(encoding='utf-8', errors='ignore').splitlines()
                if len(lines) > self.ops_ledger_max_lines:
                    keep = lines[-self.ops_ledger_keep_lines:]
                    self.ops_ledger_path.write_text("\n".join(keep) + "\n", encoding='utf-8')
            except Exception:
                pass
        except Exception:
            pass

    def _load_recent_ops(self, limit: int) -> list[dict]:
        """Load last N operation records from the JSONL ledger."""
        try:
            lines = self.ops_ledger_path.read_text(encoding='utf-8', errors='ignore').splitlines()
        except Exception:
            return []
        out = []
        import json as _json
        for line in lines[-max(0, int(limit)):] if lines else []:
            try:
                out.append(_json.loads(line))
            except Exception:
                continue
        # newest first
        out.reverse()
        return out

    def _rebuild_file_operations(self, tracked_files_count: Optional[int] = None):
        """Rewrite FileOperations.md from the JSONL ledger (newest first).

        Format: list entries with file:// links for Path(s), no tables.
        """
        import time as _time
        if _time.time() - self._last_ops_write_ts < self._write_throttle_secs:
            return
        file_path = self._get_file_log_path()
        ops = self._load_recent_ops(self.log_max_entries)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cfg_path = (Path.home() / ".wks" / "config.json").expanduser()
        cfg_url = f"file://{cfg_path}"
        # Intro + table header
        header = [
            f"Reverse chronological log of last {self.log_max_entries} file operations tracked by WKS. [config]({cfg_url})",
            "",
            "| Action | Time | Checksum | Size | Modified | θ₀ | Path |",
            "|:--|:--|--:|--:|:--|--:|:--|",
        ]
        rows = []
        def _icon_for(op:str) -> str:
            m = {
                'CREATED': '➕',
                'MODIFIED': '✏️',
                'DELETED': '🗑️',
                'MOVED': '🔀',
                'RENAMED': '📝',
            }
            return m.get(op.upper(), '📄')
        home = Path.home().resolve()
        def _disp(p: Path) -> str:
            try:
                rel = p.resolve().relative_to(home)
                return f"~/{rel.as_posix()}"
            except Exception:
                return p.resolve().as_posix()

        home = Path.home().resolve()
        def _is_within(child: Path, base: Path) -> bool:
            try:
                child.resolve().relative_to(base.resolve())
                return True
            except Exception:
                return False

        def _is_temp_or_autosave(p: Path) -> bool:
            try:
                n = p.name
                nl = n.lower()
                if n.endswith('~'):
                    return True
                if (n.startswith('#') and n.endswith('#')) or n.startswith('.#'):
                    return True
                if n.startswith('~$'):
                    return True
                if n.startswith('._'):
                    return True
                if nl in {'.ds_store', 'icon\r'}:
                    return True
                if any(nl.endswith(ext) for ext in ('.swp', '.swo', '.tmp', '.part', '.crdownload')):
                    return True
                if '.tmp' in nl:
                    return True
            except Exception:
                pass
            return False

        def _skip_ops_path(p: Path) -> bool:
            try:
                pics = home/"Pictures"
                photos = home/"Photos"
                if _is_within(p, pics) or _is_within(p, photos):
                    return True
            except Exception:
                pass
            # Hide temp/autosave artifacts
            try:
                if _is_temp_or_autosave(p):
                    return True
            except Exception:
                pass
            return False

        # Helpers for size and modified
        def _hsize(n: int) -> str:
            try:
                units = ['B','KB','MB','GB','TB']
                i = 0; f = float(n)
                while f >= 1024.0 and i < len(units)-1:
                    f /= 1024.0; i += 1
                return f"{f:0.1f} {units[i]}"
            except Exception:
                return "-"

        # Optional similarity for angle-from-empty
        simdb = None
        try:
            from .similarity import SimilarityDB as _S
            from .cli import load_config as _load
            cfg = _load(); sim = cfg.get('similarity') or {}; ext = cfg.get('extract') or {}
            if sim.get('enabled'):
                simdb = _S(
                    database_name=sim.get('database','wks_similarity'),
                    collection_name=sim.get('collection','file_embeddings'),
                    mongo_uri=sim.get('mongo_uri','mongodb://localhost:27027/'),
                    model_name=sim.get('model','all-MiniLM-L6-v2'),
                    model_path=sim.get('model_path'),
                    offline=bool(sim.get('offline', False)),
                    max_chars=int(sim.get('max_chars',200000)),
                    chunk_chars=int(sim.get('chunk_chars',1500)),
                    chunk_overlap=int(sim.get('chunk_overlap',200)),
                    extract_engine=ext.get('engine','builtin'),
                    extract_ocr=bool(ext.get('ocr', False)),
                    extract_timeout_secs=int(ext.get('timeout_secs', 30)),
                )
        except Exception:
            simdb = None

        for rec in ops:
            ts = rec.get('timestamp','')
            op = (str(rec.get('operation','')).upper() or 'OP')
            icon = _icon_for(op)
            src = rec.get('source')
            dst = rec.get('destination')
            checksum = rec.get('checksum') or 'N/A'
            a_path = Path(src) if src else None
            b_path = Path(dst) if dst else None
            a = a_path.resolve().as_uri() if a_path else None
            b = b_path.resolve().as_uri() if b_path else None
            # Skip ignored paths (e.g., Photos/Pictures)
            if a_path and _skip_ops_path(a_path):
                continue
            if b_path and _skip_ops_path(b_path):
                continue
            # Build rows; for MOVED, split into two rows: MOVE_FROM and MOVE_TO
            _fig = "\u2007"
            def make_action_cell(label: str) -> str:
                raw = f"{icon} {label}"
                pad = max(0, 14 - len(raw))
                return f"`{raw}{_fig*pad}`"
            time_cell = f"`{ts}{_fig*2}`"
            def _cells_for(p: Path) -> tuple[str,str,str]:
                # size, modified, angle0
                s_cell = "-"; m_cell = "-"; a0_cell = "-"
                try:
                    st = p.stat()
                    s_cell = _hsize(getattr(st,'st_size',0))
                    from datetime import datetime as _dt
                    m_cell = _dt.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
                if simdb is not None:
                    try:
                        emb = simdb.get_file_embedding(p)
                        ang = simdb.angle_from_empty(emb) if emb else None
                        if ang is not None:
                            a0_cell = f"{ang:0.2f}°"
                    except Exception:
                        pass
                return s_cell, m_cell, a0_cell

            if op == 'MOVED' and a_path and b_path:
                if _skip_ops_path(a_path) or _skip_ops_path(b_path):
                    continue
                s_cell, m_cell, a0_cell = _cells_for(a_path)
                from_cell = f"[{_disp(a_path)}]({a})"
                rows.append(f"| {make_action_cell('MOVE_FROM')} | {time_cell} | `{checksum}` | `{s_cell}` | `{m_cell}` | `{a0_cell}` | {from_cell} |")
                s_cell, m_cell, a0_cell = _cells_for(b_path)
                to_cell = f"[{_disp(b_path)}]({b})"
                rows.append(f"| {make_action_cell('MOVE_TO')} | {time_cell} | `{checksum}` | `{s_cell}` | `{m_cell}` | `{a0_cell}` | {to_cell} |")
            else:
                if a_path and b_path:
                    if _skip_ops_path(a_path) and _skip_ops_path(b_path):
                        continue
                    # Prefer destination for stats, but keep arrow for context
                    s_cell, m_cell, a0_cell = _cells_for(b_path)
                    path_cell = f"[{_disp(a_path)}]({a}) → [{_disp(b_path)}]({b})"
                elif a_path:
                    if _skip_ops_path(a_path):
                        continue
                    s_cell, m_cell, a0_cell = _cells_for(a_path)
                    path_cell = f"[{_disp(a_path)}]({a})"
                elif b_path:
                    if _skip_ops_path(b_path):
                        continue
                    s_cell, m_cell, a0_cell = _cells_for(b_path)
                    path_cell = f"[{_disp(b_path)}]({b})"
                else:
                    s_cell, m_cell, a0_cell = ("-","-","-")
                    path_cell = ""
                action_cell = make_action_cell(op)
                rows.append(f"| {action_cell} | {time_cell} | `{checksum}` | `{s_cell}` | `{m_cell}` | `{a0_cell}` | {path_cell} |")
        # Do not filter out blank lines; keep a true blank line before the table
        out = "\n".join(header) + ("\n" + "\n".join(rows) + "\n" if rows else "\n")
        self._atomic_write(file_path, out)
        self._last_ops_write_ts = _time.time()

    def ensure_structure(self):
        """Create vault folder structure if it doesn't exist."""
        # Ensure base path (for logs) exists
        self._base_path().mkdir(parents=True, exist_ok=True)
        # Ensure Health landing page exists
        hp = self._base_path() / 'Health.md'
        if not hp.exists():
            try:
                self._atomic_write(hp, "# Health\n\n(Initialized)\n")
            except Exception:
                pass
        # Ensure root-level category folders exist
        for directory in [
            self.links_dir,
            self.projects_dir,
            self.people_dir,
            self.topics_dir,
            self.ideas_dir,
            self.orgs_dir,
            self.records_dir,
        ]:
            if directory is not None:
                directory.mkdir(parents=True, exist_ok=True)


    def create_project_note(
        self,
        project_path: Path,
        status: str = "Active",
        description: Optional[str] = None
    ) -> Path:
        """
        Create or update a project note in Projects/ folder.

        Args:
            project_path: Path to project directory (e.g., ~/2025-WKS)
            status: Project status
            description: Optional project description

        Returns:
            Path to created note
        """
        project_name = project_path.name
        note_path = self.projects_dir / f"{project_name}.md"

        # Extract date and name from project folder
        parts = project_name.split("-", 1)
        year = parts[0] if len(parts) > 0 else ""
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

    def link_file(self, source_file: Path, preserve_structure: bool = True) -> Optional[Path]:
        """
        Create a symlink to a file in the _links/ directory.

        Args:
            source_file: File to link to
            preserve_structure: If True, mirror directory structure from home

        Returns:
            Path to created symlink, or None if failed
        """
        if not source_file.exists():
            return None

        if preserve_structure:
            # Mirror structure from home directory
            home = Path.home()
            try:
                relative = source_file.relative_to(home)
                link_path = self.links_dir / relative
            except ValueError:
                # File not under home, use project-based structure
                link_path = self.links_dir / source_file.name
        else:
            link_path = self.links_dir / source_file.name

        # Create parent directories
        link_path.parent.mkdir(parents=True, exist_ok=True)

        # Create symlink if it doesn't exist
        if not link_path.exists():
            link_path.symlink_to(source_file)

        return link_path

    def _link_rel_for_source(self, source_file: Path, preserve_structure: bool = True) -> str:
        """Compute the vault-internal wiki link target (relative) for a source file.

        Returns a path like '_links/<...>' suitable for use inside [[...]] links.
        """
        if preserve_structure:
            home = Path.home()
            try:
                relative = source_file.resolve().relative_to(home)
                return f"_links/{relative.as_posix()}"
            except Exception:
                return f"_links/{source_file.name}"
        else:
            return f"_links/{source_file.name}"

    def _iter_vault_markdown(self):
        for md in self.vault_path.rglob("*.md"):
            try:
                # Skip our log files
                if md.resolve() == self.file_log_path.resolve() or md.resolve() == self.activity_log_path.resolve():
                    continue
            except Exception:
                pass
            yield md

    def update_vault_links_on_move(self, old_path: Path, new_path: Path):
        """Update wiki links inside the vault when a file moves.

        Rewrites [[_links/<old>]] (and alias forms). Also updates legacy [[links/…]] to the new [[_links/…]] path.
        """
        old_rel = self._link_rel_for_source(old_path)
        new_rel = self._link_rel_for_source(new_path)
        if old_rel == new_rel:
            return
        # Prepare replacements for both _links and legacy links paths
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
            except Exception:
                continue
            original = content
            for a, b in patterns:
                if a in content:
                    content = content.replace(a, b)
            if content != original:
                try:
                    md.write_text(content, encoding="utf-8")
                except Exception:
                    pass

    def mark_reference_deleted(self, path: Path):
        """Annotate vault notes that reference a deleted file with a callout.

        Adds a line '> 🗑️ deleted: [[_links/...]]' near the top if not already present (supports legacy [[links/...]] references).
        """
        rel = self._link_rel_for_source(path)
        marker = f"🗑️ deleted: [[{rel}]]"
        legacy_rel = rel.replace("_links/", "links/")
        for md in self._iter_vault_markdown():
            try:
                content = md.read_text(encoding="utf-8")
            except Exception:
                continue
            if (
                f"[[{rel}]]" not in content and f"[[{rel}|" not in content and
                f"[[{legacy_rel}]]" not in content and f"[[{legacy_rel}|" not in content
            ):
                continue
            if marker in content:
                continue
            # Insert marker after first header or at top
            lines = content.splitlines()
            insert_idx = 0
            if lines and lines[0].startswith("# "):
                insert_idx = 1
            lines.insert(insert_idx, f"> {marker}")
            try:
                md.write_text("\n".join(lines) + "\n", encoding="utf-8")
            except Exception:
                pass

    def write_doc_text(self, content_hash: str, source_path: Path, text: str, keep: int = 99):
        """Write raw extracted text to WKS/Docs/<checksum>.md and keep only last N.

        Args:
            content_hash: SHA256 hex of file content
            source_path: Original file path
            text: Extracted raw text
            keep: Max number of docs to keep (delete oldest beyond this)
        """
        docs_dir = self._base_path() / 'Docs'
        docs_dir.mkdir(parents=True, exist_ok=True)
        doc_path = docs_dir / f"{content_hash}.md"
        header = (
            f"# {source_path.name}\n\n"
            f"`{source_path}`\n\n"
            f"*Checksum:* `{content_hash}`  *Updated:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "---\n\n"
        )
        try:
            doc_path.write_text(header + text, encoding='utf-8')
        except Exception:
            return
        # Rotate: keep only last N by mtime
        try:
            entries = sorted(docs_dir.glob('*.md'), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in entries[keep:]:
                try:
                    old.unlink()
                except Exception:
                    pass
        except Exception:
            pass

    def link_project(self, project_path: Path) -> list[Path]:
        """
        Create symlinks for key files in a project.

        Args:
            project_path: Path to project directory

        Returns:
            List of created symlink paths
        """
        links_created = []

        # Common files to link
        common_files = [
            "README.md",
            "SPEC.md",
            "TODO.md",
            "NOTES.md",
        ]

        for filename in common_files:
            file_path = project_path / filename
            if file_path.exists():
                link = self.link_file(file_path)
                if link:
                    links_created.append(link)

        return links_created

    def update_link_on_move(self, old_path: Path, new_path: Path):
        """
        Update symlink when a file is moved.

        Args:
            old_path: Previous file location
            new_path: New file location
        """
        # Find existing symlink
        home = Path.home()
        try:
            relative_old = old_path.relative_to(home)
            old_link = self.links_dir / relative_old

            if old_link.exists() and old_link.is_symlink():
                # Remove old link
                old_link.unlink()

                # Create new link
                self.link_file(new_path)
        except (ValueError, OSError):
            pass  # File not tracked or operation failed

    def find_broken_links(self) -> list[Path]:
        """
        Find all broken symlinks in the vault.

        Returns:
            List of broken symlink paths
        """
        broken = []

        for link in self.links_dir.rglob("*"):
            if link.is_symlink() and not link.exists():
                broken.append(link)

        return broken

    def cleanup_broken_links(self) -> int:
        """
        Remove all broken symlinks from the vault.

        Returns:
            Number of links removed
        """
        broken = self.find_broken_links()
        for link in broken:
            link.unlink()
        return len(broken)

    def _get_file_checksum(self, path: Path) -> Optional[str]:
        """
        Calculate SHA256 checksum of a file.

        Args:
            path: Path to file

        Returns:
            Hex digest of checksum, or None if file doesn't exist/can't be read
        """
        try:
            if path.exists() and path.is_file():
                sha256 = hashlib.sha256()
                with open(path, 'rb') as f:
                    for block in iter(lambda: f.read(4096), b''):
                        sha256.update(block)
                return sha256.hexdigest()[:12]  # First 12 chars for brevity
        except (OSError, PermissionError):
            pass
        return None

    def log_file_operation(
        self,
        operation: str,
        path: Path,
        destination: Optional[Path] = None,
        details: Optional[str] = None,
        tracked_files_count: Optional[int] = None
    ):
        """
        Record a file operation by appending to a JSONL ledger and rewrite the
        FileOperations.md from that ledger (newest first). This avoids fragile
        in-place table editing.
        """
        # Build record
        ts_raw = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rec = {
            "timestamp": ts_raw,
            "operation": operation,
            "source": str(path) if path else None,
            "destination": str(destination) if destination else None,
            "details": details or None,
        }
        # Compute a representative checksum (source or destination)
        try:
            src_cs = self._get_file_checksum(path)
        except Exception:
            src_cs = None
        try:
            dst_cs = self._get_file_checksum(destination) if destination else None
        except Exception:
            dst_cs = None
        rec["checksum"] = dst_cs or src_cs or None
        # Append to ledger and rebuild file
        self._append_ops_ledger(rec)
        self._rebuild_file_operations(tracked_files_count=tracked_files_count)

    def get_recent_operations(self, limit: int = 50) -> str:
        """
        Get the most recent file operations.

        Args:
            limit: Maximum number of entries to return

        Returns:
            String containing recent operations
        """
        if not self.file_log_path.exists():
            return "No operations logged yet."

        content = self.file_log_path.read_text()
        lines = content.split('\n')

        # Find entries (lines starting with '- **')
        entries = [line for line in lines if line.strip().startswith('- **')]

        return '\n'.join(entries[:limit])

    def update_active_files(self, active_files: list[tuple[str, float, float]], tracker=None):
        """Single-line ActiveFiles entries with fixed-width header and path last.

        Format: `ANGLE° · DELTA°/min · YYYY-MM-DD HH:MM:SS ·` [~/path](file:///...)
        """
        # Compact table header with rate scales; numeric columns right-aligned
        lines = [
            "| ° | °/hr | °/day | °/wk | Modified | Name |",
            "|--:|--:|--:|--:|:--|:--|",
        ]
        from datetime import datetime
        home = Path.home().resolve()

        # Load ignore rules to filter out excluded/ignored paths
        try:
            from .cli import load_config as _load
            cfg = _load(); mon = cfg.get('monitor') or {}
            exclude_paths = [Path(p).expanduser().resolve() for p in (mon.get('exclude_paths') or [])]
            ignore_dirnames = set(mon.get('ignore_dirnames') or [])
            ignore_globs = list(mon.get('ignore_globs') or [])
        except Exception:
            exclude_paths = []
            ignore_dirnames = set()
            ignore_globs = []

        def _is_within(child: Path, base: Path) -> bool:
            try:
                child.resolve().relative_to(base.resolve())
                return True
            except Exception:
                return False

        def _skip_path(p: Path) -> bool:
            # Explicit skip for ~/Pictures hierarchy
            try:
                if p.resolve().is_relative_to(Path.home().resolve()/"Pictures"):
                    return True
            except Exception:
                try:
                    (p.resolve()).relative_to(Path.home().resolve()/"Pictures")
                    return True
                except Exception:
                    pass
            if any(_is_within(p, ex) for ex in exclude_paths):
                return True
            for part in p.parts:
                if part.startswith('.') and part != '.wks':
                    return True
                if part in ignore_dirnames:
                    return True
            try:
                import fnmatch as _fn
                pstr = p.as_posix()
                for g in ignore_globs:
                    if _fn.fnmatchcase(pstr, g) or _fn.fnmatchcase(p.name, g):
                        return True
            except Exception:
                pass
            return False

        def _disp(p: Path) -> str:
            try:
                rel = p.resolve().relative_to(home)
                return f"~/{rel.as_posix()}"
            except Exception:
                return p.resolve().as_posix()

        # Prepare Mongo changes querying for windowed averages
        use_changes = True
        changes_coll = None
        try:
            from .cli import load_config as _load
            cfg2 = _load(); sim2 = cfg2.get('similarity') or {}
            if sim2.get('enabled'):
                from pymongo import MongoClient as _MC
                client = _MC(sim2.get('mongo_uri','mongodb://localhost:27027/'))
                db = client[sim2.get('database','wks_similarity')]
                changes_coll = db['embedding_changes']
            else:
                use_changes = False
        except Exception:
            use_changes = False

        import time as _time
        now_epoch = int(_time.time())
        def window_deg_per_sec(fp: str, seconds_window: int) -> float:
            if not changes_coll:
                return 0.0
            try:
                start = now_epoch - seconds_window
                total_deg = 0.0
                total_dt = 0.0
                for ev in changes_coll.find({"file_path": fp, "t_new_epoch": {"$gte": start}}):
                    d = float(ev.get('degrees') or 0.0)
                    dt = float(ev.get('seconds') or 0.0)
                    if dt > 0:
                        total_deg += d
                        total_dt += dt
                return (total_deg / total_dt) if total_dt > 0 else 0.0
            except Exception:
                return 0.0

        # Collect rows so we can sort by absolute hourly angle when embedding changes available
        rows_sorted: list[tuple[float, str]] = []

        for path_str, angle, _delta in (active_files[: self.active_files_max_rows] if isinstance(active_files, list) else active_files):
            p = Path(path_str)
            if _skip_path(p):
                continue
            # Last modified
            if tracker is not None:
                try:
                    last_mod = tracker.get_last_modified(p)
                except Exception:
                    last_mod = None
            else:
                last_mod = None
            if not last_mod:
                try:
                    # Simple readable timestamp (match FileOperations)
                    last_mod = datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    last_mod = "Unknown"
            else:
                # Normalize tracker ISO timestamps to simple format
                try:
                    from datetime import datetime as _dt
                    last_mod = _dt.fromisoformat(str(last_mod)).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    s = str(last_mod).replace('T', ' ')
                    if '.' in s:
                        s = s.split('.', 1)[0]
                    last_mod = s
            # Windowed weighted averages from embedding_changes
            if use_changes and changes_coll is not None:
                # Strict windowed averages per your definition
                dps_1h = window_deg_per_sec(path_str, 3600)
                dps_1d = window_deg_per_sec(path_str, 86400)
                dps_1w = window_deg_per_sec(path_str, 604800)
                dph = dps_1h * 3600.0
                dpd = dps_1d * 86400.0
                dpw = dps_1w * 604800.0
                # recent angle from last event
                try:
                    ev = changes_coll.find({"file_path": path_str}).sort("t_new_epoch", -1).limit(1)
                    last_deg = None
                    for e in ev:
                        last_deg = float(e.get('degrees') or 0.0)
                    if last_deg is not None:
                        angle = last_deg
                except Exception:
                    pass
            else:
                # fallback: no changes available
                dph = 0.0; dpd = 0.0; dpw = 0.0
            angle_str = f"{angle:0.2f}"
            dph_str = f"{dph:+0.2f}"
            dpd_str = f"{dpd:+0.2f}"
            dpw_str = f"{dpw:+0.2f}"
            name_cell = f"📄 [{_disp(p)}]({p.resolve().as_uri()})"
            line = f"| `{angle_str}` | `{dph_str}` | `{dpd_str}` | `{dpw_str}` | `{last_mod}` | {name_cell} |"
            # Sort by absolute hourly angle when similarity changes are available; else keep order
            key = abs(float(dph)) if (use_changes and changes_coll is not None) else 0.0
            rows_sorted.append((key, line))
        # If we collected sortable rows, sort descending by absolute hourly angle
        if rows_sorted:
            rows_sorted.sort(key=lambda t: t[0], reverse=True)
            for _, ln in rows_sorted:
                lines.append(ln)
        lines.append("")
        lines.append(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        import time as _time
        if _time.time() - self._last_active_write_ts < self._write_throttle_secs:
            return
        self._atomic_write(self.activity_log_path, "\n".join(lines) + "\n")
        self._last_active_write_ts = _time.time()

    def _atomic_write(self, path: Path, content: str):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(content)
            tmp.replace(path)
        except Exception:
            try:
                path.write_text(content, encoding='utf-8')
            except Exception:
                pass

    def write_health_page(self, *, state_file: Optional[Path] = None):
        """Write Health.md landing page with key metrics and an embedded Spec.

        - Uses ~/.wks/health.json if present
        - Counts tracked files from monitor_state.json if present
        - Shows ledger size and recent ops count
        - Tries to include similarity stats if available
        """
        import time as _time
        if _time.time() - self._last_health_write_ts < self._write_throttle_secs:
            return
        base = self._base_path()
        hp = base / 'Health.md'
        # Metrics
        from datetime import datetime as _dt
        import json as _json
        health_path = Path.home()/'.wks'/'health.json'
        health = {}
        try:
            if health_path.exists():
                health = _json.load(open(health_path, 'r'))
        except Exception:
            health = {}
        # Tracked files
        tracked = None
        try:
            sf = state_file or (Path.home()/'.wks'/'monitor_state.json')
            if sf.exists():
                ms = _json.load(open(sf, 'r'))
                tracked = len((ms.get('files') or {}))
        except Exception:
            tracked = None
        # Ledger lines
        ledger_lines = 0
        try:
            ledger_lines = len(self.ops_ledger_path.read_text(encoding='utf-8', errors='ignore').splitlines())
        except Exception:
            pass
        # Similarity stats
        sim_stats = None
        try:
            from .similarity import SimilarityDB as _S
            # Use default config locations via a local loader
            from .cli import load_config as _load
            cfg = _load(); sim = cfg.get('similarity') or {}
            if sim.get('enabled'):
                db = _S(database_name=sim.get('database','wks_similarity'), collection_name=sim.get('collection','file_embeddings'), mongo_uri=sim.get('mongo_uri','mongodb://localhost:27027/'), model_name=sim.get('model','all-MiniLM-L6-v2'))
                sim_stats = db.get_stats()
        except Exception:
            sim_stats = None
        # Build compact metrics-only table
        def _age_str(secs):
            try:
                secs = int(secs)
                if secs < 60:
                    return f"{secs}s"
                mins = secs // 60
                if mins < 60:
                    return f"{mins}m"
                hrs = mins // 60
                return f"{hrs}h"
            except Exception:
                return "—"

        heartbeat_iso = health.get('heartbeat_iso', '')
        uptime_hms = health.get('uptime_hms', '—')
        bpm = health.get('avg_beats_per_min', '—')
        try:
            bpm_str = f"{float(bpm):.1f}"
        except Exception:
            bpm_str = str(bpm)
        pdel = health.get('pending_deletes', 0)
        pmod = health.get('pending_mods', 0)
        lerr = health.get('last_error')
        lerr_age = _age_str(health.get('last_error_age_secs') or 0)

        ops_path = (base/'FileOperations.md').as_posix()
        act_path = (base/'ActiveFiles.md').as_posix()

        pid = health.get('pid', '—')
        ok_flag = 'true' if not lerr else 'false'
        last_err_age = health.get('last_error_age_secs')
        lock_present = health.get('lock_present')
        lock_pid = health.get('lock_pid')
        lines = [
            '| Metric | Value | Info |',
            '|:--|:--|:--|',
            f"| 🟢 Last Update | `{heartbeat_iso}` | Health tick time |",
            f"| 🕒 Uptime | `{uptime_hms}` | Since last restart |",
            f"| 🫀 BPM | `{bpm_str}` | Average beats/min (ticks + ops) |",
            f"| 🧩 PID | `{pid}` | Daemon process ID |",
            f"| 🧰 Pending deletes | `{pdel}` | Pending coalesced ops |",
            f"| 🧰 Pending mods | `{pmod}` | Pending coalesced ops |",
            f"| ✅ OK | `{ok_flag}` | Most recent error or OK |",
            f"| 📁 Tracked files | `{tracked if tracked is not None else '—'}` | [Active](WKS/ActiveFiles) |",
            f"| 🧾 Ledger entries | `{ledger_lines}` | [Ops](WKS/FileOperations) |",
            f"| 🔒 Lock present | `{str(bool(lock_present)).lower()}` | Lock file currently exists |",
            f"| 🧷 Lock pid | `{lock_pid if lock_pid is not None else '—'}` | PID recorded in lock file |",
        ]
        if sim_stats:
            total = sim_stats.get('total_files', 0)
            lines += [f"| 🗃️ Similarity files | `{total}` | Indexed files |"]
        # Divider and spec embed below, outside metrics
        lines += ['','---','![[SPEC]]']
        self._atomic_write(hp, "\n".join(lines) + "\n")
        self._last_health_write_ts = _time.time()


if __name__ == "__main__":
    # Example usage
    from rich.console import Console

    console = Console()

    vault = ObsidianVault(Path.home() / "obsidian")
    vault.ensure_structure()

    console.print("[green]Vault structure created![/green]")

    # Create a project note
    wks_project = Path.home() / "2025-WKS"
    if wks_project.exists():
        note = vault.create_project_note(
            wks_project,
            description="Wieselquist Knowledge System - AI-assisted file organization"
        )
        console.print(f"[blue]Created project note:[/blue] {note}")

        # Link project files
        links = vault.link_project(wks_project)
        console.print(f"[yellow]Created {len(links)} symlinks[/yellow]")
