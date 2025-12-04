from pathlib import Path
from unittest.mock import patch

import pytest

from wks.vault.git_hooks import install_hooks, is_hook_installed, uninstall_hooks


class TestGitHooks:
    @pytest.fixture
    def mock_paths(self, tmp_path):
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        git_dir = vault_path / ".git"
        git_dir.mkdir()
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir()
        return vault_path, hooks_dir

    @patch("wks.vault.git_hooks.get_hook_source_path")
    def test_install_hooks_success(self, mock_source, mock_paths):
        vault_path, _hooks_dir = mock_paths
        mock_source.return_value = Path("/tmp/source_hook")

        # Create dummy source
        with patch("shutil.copy2") as mock_copy, patch("pathlib.Path.chmod") as mock_chmod:
            assert install_hooks(vault_path) is True
            mock_copy.assert_called()
            mock_chmod.assert_called_with(0o755)

    def test_install_hooks_no_git(self, tmp_path):
        vault_path = tmp_path / "vault"
        vault_path.mkdir()

        with pytest.raises(RuntimeError, match="Not a git repository"):
            install_hooks(vault_path)

    @patch("wks.vault.git_hooks.get_hook_source_path")
    def test_install_hooks_exists_no_force(self, mock_source, mock_paths):
        vault_path, hooks_dir = mock_paths
        mock_source.return_value = Path("/tmp/source_hook")

        # Create existing hook
        hook_path = hooks_dir / "pre-commit"
        hook_path.touch()

        with pytest.raises(FileExistsError):
            install_hooks(vault_path, force=False)

    @patch("wks.vault.git_hooks.get_hook_source_path")
    def test_install_hooks_exists_force(self, mock_source, mock_paths):
        vault_path, hooks_dir = mock_paths
        mock_source.return_value = Path("/tmp/source_hook")

        # Create existing hook
        hook_path = hooks_dir / "pre-commit"
        hook_path.touch()

        with patch("shutil.copy2") as mock_copy, patch("pathlib.Path.chmod"):
            assert install_hooks(vault_path, force=True) is True
            mock_copy.assert_called()

    def test_uninstall_hooks_success(self, mock_paths):
        vault_path, hooks_dir = mock_paths
        hook_path = hooks_dir / "pre-commit"
        hook_path.touch()

        assert uninstall_hooks(vault_path) is True
        assert not hook_path.exists()

    def test_uninstall_hooks_not_installed(self, mock_paths):
        vault_path, _ = mock_paths
        assert uninstall_hooks(vault_path) is True

    def test_is_hook_installed(self, mock_paths):
        vault_path, hooks_dir = mock_paths
        hook_path = hooks_dir / "pre-commit"

        assert is_hook_installed(vault_path) is False

        hook_path.touch()
        # Mock stat mode to be executable
        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_mode = 0o100755
            assert is_hook_installed(vault_path) is True

            mock_stat.return_value.st_mode = 0o100644
            assert is_hook_installed(vault_path) is False
