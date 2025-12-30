"""Unit tests for Obsidian vault scanner."""

from pathlib import Path

import pytest

from wks.api.vault._obsidian._Backend import _Backend
from wks.api.vault._obsidian._Scanner import _Scanner
from wks.api.vault.VaultConfig import VaultConfig


@pytest.fixture
def scanner(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    backend = _Backend(cfg)
    return _Scanner(backend)


def test_scanner_note_to_uri_outside_vault(scanner, tmp_path):
    """Test _note_to_uri when note is outside vault (hits line 39-43)."""
    outside_file = tmp_path / "outside.md"
    outside_file.touch()

    uri = scanner._note_to_uri(outside_file)
    assert uri.startswith("file://")


def test_scanner_scan_skips_non_md_when_provided(scanner, tmp_path):
    """Test that scan skips non-md files when a list is provided (hits line 59)."""
    vault_dir = scanner.vault.vault_path
    f1 = vault_dir / "note.md"
    f1.write_text("# Note")
    f2 = vault_dir / "data.txt"
    f2.write_text("data")

    scanner.scan(files=[f1, f2])


def test_scanner_scan_read_error(scanner, tmp_path):
    """Test handling of read errors during scan (hits line 71-73)."""
    vault_dir = scanner.vault.vault_path
    unreadable = vault_dir / "unreadable.md"
    unreadable.write_text("# Secret")
    unreadable.chmod(0o000)

    try:
        scanner.scan(files=[unreadable])
        assert scanner.stats.notes_scanned == 1
        assert len(scanner.stats.errors) == 1
        assert "unreadable.md" in scanner.stats.errors[0]
    finally:
        unreadable.chmod(0o644)


def test_scanner_rewrite_error(scanner, tmp_path):
    """Test handling of rewrite errors (hits line 103-104)."""
    vault_dir = scanner.vault.vault_path
    note = vault_dir / "note.md"
    # Create a file:// URL that will trigger a rewrite
    target = tmp_path / "target.txt"
    target.touch()
    note.write_text(f"[link](file://{target})")

    # Scan once to collect rewrites
    scanner.scan(files=[note])
    assert len(scanner._file_url_rewrites) == 1

    # Reset scanner state but keep the collected rewrites
    scanner._notes_scanned = 0
    scanner._errors = []

    # Make note unwriteable for the rewrite phase
    note.chmod(0o444)
    try:
        scanner._apply_file_url_rewrites()
        assert any("Failed to rewrite" in err for err in scanner._errors)
    finally:
        note.chmod(0o644)


def test_scanner_preview_long_line(scanner, tmp_path):
    """Test preview truncation for long lines (hits line 167)."""
    vault_dir = scanner.vault.vault_path
    long_line = "A" * 500 + " [[Target]]"
    note = vault_dir / "note.md"
    note.write_text(long_line)

    records = scanner.scan(files=[note])
    assert len(records) == 1
    # raw_line should be truncated (MAX_LINE_PREVIEW=400)
    assert "…" in records[0].raw_line
    assert len(records[0].raw_line) == 401


def test_scanner_convert_file_url_to_symlink_dir(scanner, tmp_path):
    """Test skipping directory conversion in _convert_file_url_to_symlink (hits line 211-214)."""
    vault_dir = scanner.vault.vault_path
    some_dir = tmp_path / "some_dir"
    some_dir.mkdir()

    note = vault_dir / "note.md"
    note.write_text(f"[dir](file://{some_dir})")

    records = scanner.scan(files=[note])
    # Should be a markdown_url, not a wikilink
    assert len(records) == 1
    assert records[0].link_type == "markdown_url"
    assert records[0].raw_target.startswith("file://")


def test_scanner_convert_file_url_exception(scanner, monkeypatch, tmp_path):
    """Test exception handling in _convert_file_url_to_symlink (hits line 231-233)."""
    scanner._errors = []
    # Ensure the file exists so it doesn't return early at line 214
    target = tmp_path / "x"
    target.touch()

    # Force platform.node() to raise Exception to trigger line 231
    import wks.api.vault._obsidian._Scanner as scanner_mod

    def mock_node():
        raise Exception("fail")

    monkeypatch.setattr(scanner_mod.platform, "node", mock_node)

    res = scanner._convert_file_url_to_symlink(f"file://{target}", Path("note.md"), 1, "alias")
    assert res is None
    assert len(scanner._errors) > 0
    assert any("Failed to convert file URL" in err for err in scanner._errors)


def test_scanner_note_to_uri_outside_vault_scan(scanner, tmp_path):
    """Test scan with a file outside vault (hits line 66-67)."""
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("# Outside")
    # If we pass files = [outside_file], relative_to(vault_path) will raise ValueError
    scanner.scan(files=[outside_file])
    assert scanner.stats.notes_scanned == 1


def test_scanner_convert_file_url_not_file(scanner):
    """Test _convert_file_url_to_symlink with non-file URL (hits line 200)."""
    res = scanner._convert_file_url_to_symlink("https://example.com", Path("note.md"), 1, "alias")
    assert res is None
