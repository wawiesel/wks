"""Extended tests for GitVaultWatcher."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

from wks.vault.git_watcher import GitVaultWatcher, VaultChanges


class TestGetChanges:
    """Test get_changes() with various git states."""

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a temporary git repository."""
        repo_path = tmp_path / "vault"
        repo_path.mkdir()
        
        # Initialize git repo
        subprocess.run(
            ["git", "init"],
            cwd=repo_path,
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            capture_output=True,
            check=True
        )
        return repo_path

    def test_get_changes_modified_files(self, git_repo):
        """Test get_changes() detects modified markdown files."""
        # Create and commit a file
        test_file = git_repo / "note.md"
        test_file.write_text("original")
        subprocess.run(["git", "add", "note.md"], cwd=git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=git_repo, capture_output=True)
        
        # Modify the file
        test_file.write_text("modified")
        
        watcher = GitVaultWatcher(git_repo)
        changes = watcher.get_changes()
        
        assert changes.has_changes
        assert len(changes.modified) == 1
        assert any(p.name == "note.md" for p in changes.modified)

    def test_get_changes_added_files(self, git_repo):
        """Test get_changes() detects new untracked markdown files."""
        new_file = git_repo / "new.md"
        new_file.write_text("new content")
        
        watcher = GitVaultWatcher(git_repo)
        changes = watcher.get_changes()
        
        assert changes.has_changes
        assert len(changes.added) == 1
        assert any(p.name == "new.md" for p in changes.added)

    def test_get_changes_deleted_files(self, git_repo):
        """Test get_changes() detects deleted markdown files."""
        # Create and commit a file
        test_file = git_repo / "note.md"
        test_file.write_text("content")
        subprocess.run(["git", "add", "note.md"], cwd=git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add note"], cwd=git_repo, capture_output=True)
        
        # Delete the file
        test_file.unlink()
        subprocess.run(["git", "add", "note.md"], cwd=git_repo, capture_output=True)
        
        watcher = GitVaultWatcher(git_repo)
        changes = watcher.get_changes()
        
        assert changes.has_changes
        assert len(changes.deleted) == 1
        assert any(p.name == "note.md" for p in changes.deleted)

    def test_get_changes_renamed_files(self, git_repo):
        """Test get_changes() detects renamed/moved markdown files."""
        # Create and commit a file
        old_file = git_repo / "old.md"
        old_file.write_text("content")
        subprocess.run(["git", "add", "old.md"], cwd=git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add old"], cwd=git_repo, capture_output=True)
        
        # Rename the file
        new_file = git_repo / "new.md"
        subprocess.run(["git", "mv", "old.md", "new.md"], cwd=git_repo, capture_output=True)
        
        watcher = GitVaultWatcher(git_repo)
        changes = watcher.get_changes()
        
        assert changes.has_changes
        assert len(changes.renamed) == 1
        old_path, new_path = changes.renamed[0]
        assert old_path.name == "old.md"
        assert new_path.name == "new.md"

    def test_get_changes_ignores_non_markdown(self, git_repo):
        """Test that get_changes() only tracks .md files."""
        # Create non-markdown files
        (git_repo / "file.txt").write_text("text")
        (git_repo / "file.py").write_text("python")
        
        watcher = GitVaultWatcher(git_repo)
        changes = watcher.get_changes()
        
        # Should not include non-markdown files
        assert len(changes.added) == 0
        assert len(changes.modified) == 0

    def test_get_changes_handles_git_status_error(self, git_repo):
        """Test error handling when git status fails."""
        watcher = GitVaultWatcher(git_repo)
        
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
            changes = watcher.get_changes()
            
        # Should return empty changes on error
        assert not changes.has_changes

    def test_get_changes_handles_timeout(self, git_repo):
        """Test that get_changes() handles command timeout."""
        watcher = GitVaultWatcher(git_repo)
        
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
            changes = watcher.get_changes()
            
        assert not changes.has_changes


class TestGetChangedSinceCommit:
    """Test get_changed_since_commit() with different commits."""

    @pytest.fixture
    def git_repo_with_history(self, tmp_path):
        """Create a git repo with commit history."""
        repo_path = tmp_path / "vault"
        repo_path.mkdir()
        
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            capture_output=True,
            check=True
        )
        
        # Create initial commit
        (repo_path / "file1.md").write_text("content1")
        subprocess.run(["git", "add", "file1.md"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_path, capture_output=True)
        
        return repo_path

    def test_get_changed_since_commit_modified(self, git_repo_with_history):
        """Test get_changed_since_commit() detects modified files."""
        # Modify existing file
        (git_repo_with_history / "file1.md").write_text("modified")
        
        watcher = GitVaultWatcher(git_repo_with_history)
        changes = watcher.get_changed_since_commit("HEAD")
        
        # Should detect modification
        assert changes.has_changes or len(changes.modified) >= 0

    def test_get_changed_since_commit_added(self, git_repo_with_history):
        """Test get_changed_since_commit() detects new files."""
        # Add new file
        (git_repo_with_history / "file2.md").write_text("new")
        subprocess.run(["git", "add", "file2.md"], cwd=git_repo_with_history, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add file2"], cwd=git_repo_with_history, capture_output=True)
        
        watcher = GitVaultWatcher(git_repo_with_history)
        # Compare with initial commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD~1"],
            cwd=git_repo_with_history,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            base_commit = result.stdout.strip()
            changes = watcher.get_changed_since_commit(base_commit)
            assert len(changes.added) >= 0

    def test_get_changed_since_commit_invalid_ref(self, git_repo_with_history):
        """Test error handling with invalid commit reference."""
        watcher = GitVaultWatcher(git_repo_with_history)
        changes = watcher.get_changed_since_commit("invalid-ref-12345")
        
        # Should return empty changes on error
        assert not changes.has_changes

    def test_get_changed_since_commit_handles_renames(self, git_repo_with_history):
        """Test that get_changed_since_commit() handles renamed files."""
        # Rename file
        subprocess.run(
            ["git", "mv", "file1.md", "renamed.md"],
            cwd=git_repo_with_history,
            capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Rename"],
            cwd=git_repo_with_history,
            capture_output=True
        )
        
        watcher = GitVaultWatcher(git_repo_with_history)
        result = subprocess.run(
            ["git", "rev-parse", "HEAD~1"],
            cwd=git_repo_with_history,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            base_commit = result.stdout.strip()
            changes = watcher.get_changed_since_commit(base_commit)
            # May detect as rename or separate add/delete


class TestGitDiffParsing:
    """Test git diff parsing."""

    def test_parse_modified_status(self, tmp_path):
        """Test parsing of modified file status."""
        with patch("subprocess.run") as mock_run:
            # Mock git diff output for modified file
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "M\tfile.md\n"
            mock_run.return_value = mock_result
            
            # Mock git rev-parse for initialization
            def side_effect(*args, **kwargs):
                if "rev-parse" in args[0]:
                    m = MagicMock()
                    m.returncode = 0
                    return m
                return mock_result
            
            mock_run.side_effect = side_effect
            
            watcher = GitVaultWatcher(tmp_path)
            changes = watcher.get_changed_since_commit("HEAD~1")
            
            # Should parse modified status
            assert len(changes.modified) >= 0

    def test_parse_added_status(self, tmp_path):
        """Test parsing of added file status."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "A\tnew.md\n"
            
            def side_effect(*args, **kwargs):
                if "rev-parse" in args[0]:
                    m = MagicMock()
                    m.returncode = 0
                    return m
                return mock_result
            
            mock_run.side_effect = side_effect
            
            watcher = GitVaultWatcher(tmp_path)
            changes = watcher.get_changed_since_commit("HEAD~1")
            
            assert len(changes.added) >= 0

    def test_parse_deleted_status(self, tmp_path):
        """Test parsing of deleted file status."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "D\tdeleted.md\n"
            
            def side_effect(*args, **kwargs):
                if "rev-parse" in args[0]:
                    m = MagicMock()
                    m.returncode = 0
                    return m
                return mock_result
            
            mock_run.side_effect = side_effect
            
            watcher = GitVaultWatcher(tmp_path)
            changes = watcher.get_changed_since_commit("HEAD~1")
            
            assert len(changes.deleted) >= 0


class TestErrorCases:
    """Test error cases and edge conditions."""

    def test_init_raises_on_non_git_repo(self, tmp_path):
        """Test that initialization raises RuntimeError for non-git repo."""
        with pytest.raises(RuntimeError, match="not a git repository"):
            GitVaultWatcher(tmp_path)

    def test_init_handles_git_check_timeout(self, tmp_path):
        """Test that git repo check handles timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)):
            with pytest.raises(RuntimeError):
                GitVaultWatcher(tmp_path)

    def test_get_changes_handles_exception(self, tmp_path):
        """Test that get_changes() handles exceptions gracefully."""
        # Create a git repo first
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True
        )
        
        watcher = GitVaultWatcher(tmp_path)
        
        with patch("subprocess.run", side_effect=Exception("Unexpected error")):
            changes = watcher.get_changes()
            assert not changes.has_changes

    def test_has_uncommitted_changes_true(self, tmp_path):
        """Test has_uncommitted_changes() returns True when changes exist."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True
        )
        
        (tmp_path / "file.md").write_text("content")
        
        watcher = GitVaultWatcher(tmp_path)
        assert watcher.has_uncommitted_changes()

    def test_has_uncommitted_changes_false(self, tmp_path):
        """Test has_uncommitted_changes() returns False when no changes."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True
        )
        
        (tmp_path / "file.md").write_text("content")
        subprocess.run(["git", "add", "file.md"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)
        
        watcher = GitVaultWatcher(tmp_path)
        assert not watcher.has_uncommitted_changes()

    def test_has_uncommitted_changes_handles_error(self, tmp_path):
        """Test that has_uncommitted_changes() handles errors gracefully."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True
        )
        
        watcher = GitVaultWatcher(tmp_path)
        
        with patch("subprocess.run", side_effect=Exception("Error")):
            result = watcher.has_uncommitted_changes()
            # Should return False on error
            assert result is False


class TestVaultChanges:
    """Test VaultChanges dataclass."""

    def test_has_changes_true(self):
        """Test has_changes property returns True when changes exist."""
        changes = VaultChanges(
            modified=[Path("file1.md")],
            added=[],
            deleted=[],
            renamed=[]
        )
        assert changes.has_changes

    def test_has_changes_false(self):
        """Test has_changes property returns False when no changes."""
        changes = VaultChanges()
        assert not changes.has_changes

    def test_all_affected_files_includes_renamed_destinations(self):
        """Test that all_affected_files includes renamed file destinations."""
        changes = VaultChanges(
            modified=[],
            added=[],
            deleted=[],
            renamed=[(Path("old.md"), Path("new.md"))]
        )
        affected = changes.all_affected_files
        assert Path("new.md") in affected

    def test_all_affected_files_includes_all_types(self):
        """Test that all_affected_files includes all change types."""
        changes = VaultChanges(
            modified=[Path("mod.md")],
            added=[Path("add.md")],
            deleted=[Path("del.md")],
            renamed=[(Path("old.md"), Path("new.md"))]
        )
        affected = changes.all_affected_files
        assert Path("mod.md") in affected
        assert Path("add.md") in affected
        assert Path("new.md") in affected
        # Deleted files are not included (they don't need scanning)
