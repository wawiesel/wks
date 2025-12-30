"""Unit tests for Obsidian vault backend."""

from __future__ import annotations

from pathlib import Path

import pytest

from wks.api.vault._obsidian._Backend import _Backend
from wks.api.vault.VaultConfig import VaultConfig


@pytest.fixture
def vault_dir(tmp_path):
    d = tmp_path / "vault"
    d.mkdir()
    (d / "note.md").touch()
    links_dir = d / "_links"
    links_dir.mkdir()
    return d


def test_backend_init(vault_dir):
    cfg = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    backend = _Backend(cfg)
    assert backend.vault_path == vault_dir
    assert backend.links_dir == vault_dir / "_links"


def test_backend_resolve_link_relative(vault_dir):
    cfg = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    backend = _Backend(cfg)

    # note.md exists
    metadata = backend.resolve_link("note.md")
    assert metadata.status == "ok"
    assert metadata.target_uri == "vault:///note.md"


def test_backend_resolve_link_broken(vault_dir):
    cfg = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    backend = _Backend(cfg)

    metadata = backend.resolve_link("missing.md")
    assert metadata.status == "broken"


def test_backend_resolve_link_links_dir_fallback(vault_dir, tmp_path):
    cfg = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    backend = _Backend(cfg)

    # Symlink in _links pointing to something
    target = tmp_path / "external.txt"
    target.touch()
    link_path = vault_dir / "_links" / "test.txt"
    link_path.symlink_to(target)

    metadata = backend.resolve_link("_links/test.txt")
    # Should fall back to f"file://{resolved}"
    assert metadata.target_uri.startswith("file://")


def test_backend_iter_markdown_files_skip_non_file(tmp_path):
    vault_dir = tmp_path / "vault_skip"
    vault_dir.mkdir()
    # Create a directory ending in .md
    subdir = vault_dir / "subdir.md"
    subdir.mkdir()
    (vault_dir / "real.md").touch()

    cfg = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    backend = _Backend(cfg)

    files = list(backend.iter_markdown_files())
    assert len(files) == 1
    assert not any("subdir.md" in str(f) for f in files)


def test_backend_relative_to_exception(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault_rel"
    vault_dir.mkdir()
    (vault_dir / "note.md").touch()

    cfg = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    backend = _Backend(cfg)

    # Mock relative_to to raise
    monkeypatch.setattr(Path, "relative_to", lambda self, other: exec('raise ValueError("fail")'))

    files = list(backend.iter_markdown_files())
    assert len(files) == 0


def test_backend_iter_markdown_files_yield_exception(tmp_path):
    """Test handling exception during yield (line 63-64)."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "note1.md").touch()
    (vault_dir / "note2.md").touch()

    cfg = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    backend = _Backend(cfg)

    gen = backend.iter_markdown_files()
    next(gen)
    # throw() returns next yielded value if caught.
    # We need a second file to be yielded after the first one's yield raises.
    # Ensure it's caught and continues.
    try:
        res = gen.throw(PermissionError("Denied"))
        assert res is not None
        assert "note2.md" in str(res)
    except StopIteration:
        pytest.fail("Generator stopped instead of continuing")
