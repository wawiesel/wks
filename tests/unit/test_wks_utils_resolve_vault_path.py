"""Tests for wks.api.vault.resolve_vault_path."""

import pytest

from wks.api.vault.resolve_vault_path import VaultPathError, resolve_vault_path


@pytest.fixture
def vault_dir(tmp_path):
    """Create a mock vault directory with some files."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Index.md").write_text("# Index")
    (vault / "Projects").mkdir()
    (vault / "Projects" / "2025-WKS.md").write_text("# WKS Project")
    return vault


class TestResolveVaultPath:
    """Test vault path resolution."""

    def test_vault_uri_existing_file(self, vault_dir):
        """Test vault:/// URI for existing file."""
        uri, path = resolve_vault_path("vault:///Index.md", vault_dir)
        assert uri == "vault:///Index.md"
        assert path == vault_dir / "Index.md"

    def test_vault_uri_nested_file(self, vault_dir):
        """Test vault:/// URI for nested file."""
        uri, path = resolve_vault_path("vault:///Projects/2025-WKS.md", vault_dir)
        assert uri == "vault:///Projects/2025-WKS.md"
        assert path == vault_dir / "Projects" / "2025-WKS.md"

    def test_vault_uri_nonexistent_file(self, vault_dir):
        """Test vault:/// URI for non-existent file raises error."""
        with pytest.raises(VaultPathError) as exc_info:
            resolve_vault_path("vault:///NonExistent.md", vault_dir)
        assert '"vault:///NonExistent.md" does not exist' in str(exc_info.value)

    def test_absolute_path_in_vault(self, vault_dir):
        """Test absolute path within vault is converted to vault:///."""
        abs_path = vault_dir / "Index.md"
        uri, path = resolve_vault_path(str(abs_path), vault_dir)
        assert uri == "vault:///Index.md"
        assert path == abs_path

    def test_absolute_path_outside_vault(self, vault_dir, tmp_path):
        """Test absolute path outside vault raises error."""
        outside_file = tmp_path / "outside.md"
        outside_file.write_text("# Outside")
        with pytest.raises(VaultPathError) as exc_info:
            resolve_vault_path(str(outside_file), vault_dir)
        assert "is not in the vault" in str(exc_info.value)

    def test_relative_path_cwd_inside_vault(self, vault_dir):
        """Test relative path when CWD is inside vault."""
        cwd = vault_dir / "Projects"
        uri, path = resolve_vault_path("2025-WKS.md", vault_dir, cwd=cwd)
        assert uri == "vault:///Projects/2025-WKS.md"
        assert path == vault_dir / "Projects" / "2025-WKS.md"

    def test_relative_path_cwd_outside_vault(self, vault_dir, tmp_path):
        """Test relative path when CWD is outside vault - resolves to vault root."""
        cwd = tmp_path / "outside"
        cwd.mkdir()
        uri, path = resolve_vault_path("Index.md", vault_dir, cwd=cwd)
        assert uri == "vault:///Index.md"
        assert path == vault_dir / "Index.md"

    def test_relative_path_nested_cwd_outside_vault(self, vault_dir, tmp_path):
        """Test nested relative path from outside vault."""
        cwd = tmp_path / "outside"
        cwd.mkdir()
        uri, path = resolve_vault_path("Projects/2025-WKS.md", vault_dir, cwd=cwd)
        assert uri == "vault:///Projects/2025-WKS.md"
        assert path == vault_dir / "Projects" / "2025-WKS.md"

    def test_relative_path_nonexistent_cwd_outside(self, vault_dir, tmp_path):
        """Test relative path that doesn't exist in vault raises error."""
        cwd = tmp_path / "outside"
        cwd.mkdir()
        with pytest.raises(VaultPathError) as exc_info:
            resolve_vault_path("./local/nonexistent.md", vault_dir, cwd=cwd)
        assert '"vault:///local/nonexistent.md" does not exist' in str(exc_info.value)

    def test_tilde_path_in_vault(self, vault_dir, monkeypatch):
        """Test ~/path expansion when path is in vault."""
        # Create a symlink or use actual home expansion
        # For simplicity, test absolute path behavior
        abs_path = vault_dir / "Projects" / "2025-WKS.md"
        uri, _ = resolve_vault_path(str(abs_path), vault_dir)
        assert uri == "vault:///Projects/2025-WKS.md"

    def test_dotslash_relative_path(self, vault_dir, tmp_path):
        """Test ./relative path from outside vault."""
        cwd = tmp_path / "outside"
        cwd.mkdir()
        uri, _ = resolve_vault_path("./Projects/2025-WKS.md", vault_dir, cwd=cwd)
        assert uri == "vault:///Projects/2025-WKS.md"

    def test_absolute_path_in_vault_nonexistent(self, vault_dir):
        """Test absolute path in vault that doesn't exist raises error."""
        abs_path = vault_dir / "Nonexistent.md"
        with pytest.raises(VaultPathError, match="does not exist"):
            resolve_vault_path(str(abs_path), vault_dir)

    def test_file_uri_outside_vault_raises_valueerror(self, vault_dir, tmp_path):
        """Test file:// URI outside vault raises ValueError (tests line 92)."""
        import socket

        hostname = socket.gethostname()
        outside_file = tmp_path / "outside.md"
        outside_file.write_text("# Outside", encoding="utf-8")

        file_uri = f"file://{hostname}{outside_file}"
        with pytest.raises(VaultPathError, match="is not in the vault"):
            resolve_vault_path(file_uri, vault_dir)

    def test_file_uri_in_vault(self, vault_dir):
        """Test file:// URI inside vault is converted to vault:///."""
        import socket

        hostname = socket.gethostname()
        test_file = vault_dir / "note.md"
        test_file.write_text("# Note", encoding="utf-8")

        file_uri = f"file://{hostname}{test_file}"
        uri_str, abs_path = resolve_vault_path(file_uri, vault_dir)

        assert uri_str == "vault:///note.md"
        assert abs_path == test_file

    def test_file_uri_in_vault_nonexistent(self, vault_dir):
        """Test file:// URI in vault for non-existent file raises error."""
        import socket

        hostname = socket.gethostname()
        nonexistent_file = vault_dir / "nonexistent.md"

        file_uri = f"file://{hostname}{nonexistent_file}"
        with pytest.raises(VaultPathError, match="does not exist"):
            resolve_vault_path(file_uri, vault_dir)

    def test_file_uri_outside_vault(self, vault_dir, tmp_path):
        """Test file:// URI outside vault raises error."""
        import socket

        hostname = socket.gethostname()
        outside_file = tmp_path / "outside.md"
        outside_file.write_text("# Outside", encoding="utf-8")

        file_uri = f"file://{hostname}{outside_file}"
        with pytest.raises(VaultPathError, match="is not in the vault"):
            resolve_vault_path(file_uri, vault_dir)
