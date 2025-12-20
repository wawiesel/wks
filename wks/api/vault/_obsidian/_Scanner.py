"""Vault link scanner (private)."""

from __future__ import annotations

import platform
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from wks.api.config.WKSConfig import WKSConfig
from wks.api.log.append_log import append_log

from .._AbstractBackend import _AbstractBackend
from .._constants import (
    LINK_TYPE_EMBED,
    LINK_TYPE_MARKDOWN_URL,
    LINK_TYPE_WIKILINK,
    MAX_LINE_PREVIEW,
    STATUS_OK,
)
from ._Data import _EdgeRecord, _ScanStats
from ._LinkResolver import _LinkResolver
from ._MarkdownParser import extract_headings, parse_markdown_urls, parse_wikilinks


class _Scanner:
    """Parse Obsidian markdown for wiki links and URLs."""

    def __init__(self, vault: _AbstractBackend):
        self.vault = vault
        self.link_resolver = _LinkResolver(vault.vault_path, vault.links_dir)
        self._file_url_rewrites: list[tuple[Path, int, str, str]] = []

    def _note_to_uri(self, note_path: Path) -> str:
        """Convert note path to vault:/// URI."""
        try:
            rel_path = note_path.relative_to(self.vault.vault_path)
            return f"vault:///{rel_path}"
        except ValueError:
            # Path is outside vault, fall back to file:// URI
            from ....utils.path_to_uri import path_to_uri

            return path_to_uri(note_path)

    def scan(self, files: list[Path] | None = None) -> list[_EdgeRecord]:
        """Scan vault for links."""
        records: list[_EdgeRecord] = []
        self._errors: list[str] = []
        self._notes_scanned = 0
        self._scanned_file_paths: set[str] = set()
        self._type_counts: Counter[str] = Counter()
        self._status_counts: Counter[str] = Counter()
        self._file_url_rewrites = []

        files_to_scan = files if files is not None else list(self.vault.iter_markdown_files())

        for note_path in files_to_scan:
            if files is not None and note_path.suffix != ".md":
                continue

            self._notes_scanned += 1

            try:
                rel_path = note_path.relative_to(self.vault.vault_path).as_posix()
                self._scanned_file_paths.add(rel_path)
            except ValueError:
                pass

            try:
                text = note_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError, PermissionError) as exc:
                self._errors.append(f"Cannot read {note_path}: {exc}")
                continue
            records.extend(self._parse_note(note_path, text))

        self._apply_file_url_rewrites()

        self._stats = _ScanStats(
            notes_scanned=self._notes_scanned,
            edge_total=len(records),
            type_counts=dict(self._ensure_type_keys(self._type_counts)),
            status_counts=dict(self._status_counts),
            errors=self._errors,
            scanned_files=self._scanned_file_paths,
        )
        return records

    def _apply_file_url_rewrites(self) -> None:
        """Rewrite markdown files to convert file:// URLs to [[_links/...]] wikilinks."""
        rewrites_by_note: dict[Path, list[tuple[int, str, str]]] = {}
        for note_path, line_num, old_link, new_link in self._file_url_rewrites:
            if note_path not in rewrites_by_note:
                rewrites_by_note[note_path] = []
            rewrites_by_note[note_path].append((line_num, old_link, new_link))

        for note_path, rewrites in rewrites_by_note.items():
            try:
                lines = note_path.read_text(encoding="utf-8").splitlines(keepends=True)
                for line_num, old_link, new_link in rewrites:
                    if line_num <= len(lines):
                        lines[line_num - 1] = lines[line_num - 1].replace(old_link, new_link)
                note_path.write_text("".join(lines), encoding="utf-8")
            except Exception as exc:
                self._errors.append(f"Failed to rewrite {note_path}: {exc}")

    @property
    def stats(self) -> _ScanStats:
        return self._stats

    @staticmethod
    def _ensure_type_keys(counter: Counter[str]) -> Counter[str]:
        for key in (LINK_TYPE_WIKILINK, LINK_TYPE_EMBED, LINK_TYPE_MARKDOWN_URL):
            counter.setdefault(key, 0)
        return counter

    def _parse_note(self, note_path: Path, text: str) -> list[_EdgeRecord]:
        """Parse all links from a markdown note."""
        records: list[_EdgeRecord] = []
        headings = extract_headings(text)
        lines = text.splitlines()

        for wiki_link in parse_wikilinks(text):
            record = self._build_wikilink_record(
                note_path=note_path,
                line_number=wiki_link.line_number,
                column_number=wiki_link.column_number,
                raw_line=lines[wiki_link.line_number - 1],
                heading=headings[wiki_link.line_number],
                target=wiki_link.target,
                alias=wiki_link.alias,
                is_embed=wiki_link.is_embed,
                raw_target=wiki_link.raw_target,
            )
            records.append(record)
            self._record_counts(record)

        for md_url in parse_markdown_urls(text):
            record = self._build_url_record(
                note_path=note_path,
                line_number=md_url.line_number,
                column_number=md_url.column_number,
                raw_line=lines[md_url.line_number - 1],
                heading=headings[md_url.line_number],
                url=md_url.url,
                alias=md_url.text,
            )
            records.append(record)
            self._record_counts(record)

        return records

    def _record_counts(self, record: _EdgeRecord) -> None:
        self._type_counts[record.link_type] += 1
        self._status_counts[record.status] += 1

    def _note_path(self, note_path: Path) -> str:
        return note_path.relative_to(self.vault.vault_path).as_posix()

    def _preview_line(self, line: str) -> str:
        clean = line.rstrip("\n")
        if len(clean) <= MAX_LINE_PREVIEW:
            return clean
        return f"{clean[:MAX_LINE_PREVIEW]}…"

    def _build_wikilink_record(
        self,
        note_path: Path,
        line_number: int,
        column_number: int,
        raw_line: str,
        heading: str,
        target: str,
        alias: str,
        is_embed: bool,
        raw_target: str,
    ) -> _EdgeRecord:
        note_rel = self._note_path(note_path)
        metadata = self.link_resolver.resolve(target)
        return _EdgeRecord(
            note_path=note_rel,
            from_uri=self._note_to_uri(note_path),
            line_number=line_number,
            column_number=column_number,
            source_heading=heading,
            raw_line=self._preview_line(raw_line),
            link_type=LINK_TYPE_EMBED if is_embed else LINK_TYPE_WIKILINK,
            raw_target=raw_target,
            alias_or_text=alias,
            to_uri=metadata.target_uri,
            status=metadata.status,
        )

    def _convert_file_url_to_symlink(self, url: str, note_path: Path, line_number: int, alias: str) -> str | None:
        """Convert file:// URL to _links/ symlink and record for rewriting."""
        if not url.startswith("file://"):
            return None

        try:
            parsed = urlparse(url)
            file_path = Path(parsed.path)

            if not file_path.exists():
                self._errors.append(f"File URL points to non-existent path: {url}")
                return None

            if file_path.is_dir():
                append_log(
                    WKSConfig.get_logfile_path(), "vault", "DEBUG", f"Skipping directory conversion to wikilink: {url}"
                )
                return None

            machine = platform.node().split(".")[0]
            rel_path = str(file_path).lstrip("/")
            symlink_target = f"_links/{machine}/{rel_path}"
            symlink_path = self.vault.links_dir / machine / rel_path

            if not symlink_path.exists():
                symlink_path.parent.mkdir(parents=True, exist_ok=True)
                symlink_path.symlink_to(file_path)

            old_markdown = f"[{alias}]({url})"
            new_markdown = f"[[{symlink_target}]]"
            self._file_url_rewrites.append((note_path, line_number, old_markdown, new_markdown))

            return symlink_target

        except Exception as exc:
            self._errors.append(f"Failed to convert file URL {url}: {exc}")
            return None

    def _build_url_record(
        self,
        note_path: Path,
        line_number: int,
        column_number: int,
        raw_line: str,
        heading: str,
        url: str,
        alias: str,
    ) -> _EdgeRecord:
        note_rel = self._note_path(note_path)

        if url.startswith("file://"):
            symlink_target = self._convert_file_url_to_symlink(url, note_path, line_number, alias)
            if symlink_target:
                metadata = self.link_resolver.resolve(symlink_target)
                return _EdgeRecord(
                    note_path=note_rel,
                    from_uri=self._note_to_uri(note_path),
                    line_number=line_number,
                    column_number=column_number,
                    source_heading=heading,
                    raw_line=self._preview_line(raw_line),
                    link_type=LINK_TYPE_WIKILINK,
                    raw_target=symlink_target,
                    alias_or_text=alias,
                    to_uri=metadata.target_uri,
                    status=metadata.status,
                )

        return _EdgeRecord(
            note_path=note_rel,
            from_uri=self._note_to_uri(note_path),
            line_number=line_number,
            column_number=column_number,
            source_heading=heading,
            raw_line=self._preview_line(raw_line),
            link_type=LINK_TYPE_MARKDOWN_URL,
            raw_target=url,
            alias_or_text=alias,
            to_uri=url,
            status=STATUS_OK,
        )
