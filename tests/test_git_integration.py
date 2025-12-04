from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wks.vault.git_watcher import GitVaultWatcher


class TestGitVaultWatcher:
    @patch("subprocess.run")
    def test_get_changed_files(self, mock_run):
        # Mock git rev-parse (is_git_repo)
        mock_run.return_value.returncode = 0

        watcher = GitVaultWatcher(Path("/tmp/vault"))

        # Mock git status --porcelain
        mock_status = MagicMock()
        mock_status.returncode = 0
        mock_status.stdout = "M  note.md\n?? new.md\n"

        # We need side_effect to handle multiple calls
        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "rev-parse" in cmd:
                m = MagicMock()
                m.returncode = 0
                return m
            if "status" in cmd:
                return mock_status
            return MagicMock()

        mock_run.side_effect = side_effect

        changes = watcher.get_changes()

        assert any(p.name == "note.md" for p in changes.modified)
        assert any(p.name == "new.md" for p in changes.added)

    @patch("subprocess.run")
    def test_init_error(self, mock_run):
        # Mock git rev-parse failing
        mock_run.return_value.returncode = 128

        with pytest.raises(RuntimeError):
            GitVaultWatcher(Path("/tmp/vault"))


# TODO: Add tests for git hooks if needed, but watcher coverage is main concern for indexer
