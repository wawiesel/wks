import socket

import pytest

from wks.api.vault.resolve_vault_path import VaultPathError, resolve_vault_path


@pytest.fixture
def vault_dir(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Index.md").write_text("# Index")
    (vault / "Projects").mkdir()
    (vault / "Projects" / "2025-WKS.md").write_text("# WKS Project")
    return vault


def file_uri(path) -> str:
    return f"file://{socket.gethostname()}{path}"


def write_file(path, content="# Outside"):
    path.write_text(content)
    return path


@pytest.mark.parametrize(
    ("raw_path", "cwd_relative", "expected_uri", "expected_suffix"),
    [
        ("vault:///Index.md", None, "vault:///Index.md", "Index.md"),
        ("vault:///Projects/2025-WKS.md", None, "vault:///Projects/2025-WKS.md", "Projects/2025-WKS.md"),
        ("Index.md", "outside", "vault:///Index.md", "Index.md"),
        ("Projects/2025-WKS.md", "outside", "vault:///Projects/2025-WKS.md", "Projects/2025-WKS.md"),
        ("2025-WKS.md", "Projects", "vault:///Projects/2025-WKS.md", "Projects/2025-WKS.md"),
        ("./Projects/2025-WKS.md", "outside", "vault:///Projects/2025-WKS.md", "Projects/2025-WKS.md"),
    ],
)
def test_resolve_vault_path_success(vault_dir, tmp_path, raw_path, cwd_relative, expected_uri, expected_suffix):
    if cwd_relative is None:
        cwd = None
    elif cwd_relative == "Projects":
        cwd = vault_dir / cwd_relative
    else:
        cwd = tmp_path / cwd_relative
    if cwd is not None:
        cwd.mkdir(exist_ok=True)

    uri, path = resolve_vault_path(raw_path, vault_dir, cwd=cwd)
    assert uri == expected_uri
    assert path == vault_dir / expected_suffix


def test_resolve_absolute_path_in_vault(vault_dir):
    abs_path = vault_dir / "Index.md"
    uri, path = resolve_vault_path(str(abs_path), vault_dir)
    assert uri == "vault:///Index.md"
    assert path == abs_path


@pytest.mark.parametrize(
    ("path_factory", "match"),
    [
        (lambda vault_dir, tmp_path: "vault:///NonExistent.md", '"vault:///NonExistent.md" does not exist'),
        (lambda vault_dir, tmp_path: "./local/nonexistent.md", '"vault:///local/nonexistent.md" does not exist'),
        (lambda vault_dir, tmp_path: str(vault_dir / "Nonexistent.md"), "does not exist"),
        (lambda vault_dir, tmp_path: str(write_file(tmp_path / "outside.md")), "is not in the vault"),
        (lambda vault_dir, tmp_path: file_uri(write_file(tmp_path / "outside-file-uri.md")), "is not in the vault"),
    ],
)
def test_resolve_vault_path_errors(vault_dir, tmp_path, path_factory, match):
    raw_path = path_factory(vault_dir, tmp_path)
    cwd = tmp_path / "outside"
    cwd.mkdir(exist_ok=True)
    with pytest.raises(VaultPathError, match=match):
        resolve_vault_path(raw_path, vault_dir, cwd=cwd)


def test_resolve_file_uri_in_vault(vault_dir):
    test_file = vault_dir / "note.md"
    test_file.write_text("# Note", encoding="utf-8")
    uri_str, abs_path = resolve_vault_path(file_uri(test_file), vault_dir)

    assert uri_str == "vault:///note.md"
    assert abs_path == test_file


def test_resolve_file_uri_in_vault_nonexistent(vault_dir):
    with pytest.raises(VaultPathError, match="does not exist"):
        resolve_vault_path(file_uri(vault_dir / "nonexistent.md"), vault_dir)
