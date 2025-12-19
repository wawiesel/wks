"""Unit tests for wks.api.link.cmd_prune."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_config():
    """Create a mock WKSConfig."""
    config = MagicMock()
    config.database = MagicMock()
    return config


class TestCmdPrune:
    """Tests for cmd_prune function."""

    def test_prune_removes_stale_source_links(self, mock_config, tmp_path):
        """Test that prune removes links from non-existent source files."""
        from wks.api.link.cmd_prune import cmd_prune

        # Create a temp file that exists
        existing_file = tmp_path / "existing.md"
        existing_file.write_text("# Test")
        existing_uri = f"file://testhost{existing_file}"

        # Non-existent file URI
        nonexistent_uri = f"file://testhost{tmp_path / 'deleted.md'}"

        mock_db = MagicMock()
        mock_db.find.side_effect = [
            # First call: from_uri query
            [{"from_uri": existing_uri}, {"from_uri": nonexistent_uri}],
            # Second call: to_uri query
            [],
        ]
        mock_db.delete_many.return_value = 1

        with patch("wks.api.config.WKSConfig.WKSConfig.load") as mock_load:
            mock_load.return_value = mock_config
            with patch("wks.api.link.cmd_prune.Database") as mock_database:
                mock_database.return_value.__enter__.return_value = mock_db
                mock_database.return_value.__exit__.return_value = None

                result = cmd_prune(remote=False)

                # Execute the generator
                for _ in result.progress_callback(result):
                    pass

                assert result.success is True
                assert "deleted_count" in result.output

    def test_prune_removes_stale_target_links(self, mock_config, tmp_path):
        """Test that prune removes links to non-existent local target files."""
        import platform

        from wks.api.link.cmd_prune import cmd_prune

        current_host = platform.node().split(".")[0]

        # Non-existent target file URI
        nonexistent_target = f"file://{current_host}{tmp_path / 'missing_target.md'}"

        mock_db = MagicMock()
        mock_db.find.side_effect = [
            # First call: from_uri query (no stale sources)
            [],
            # Second call: to_uri query
            [{"to_uri": nonexistent_target}],
        ]
        mock_db.delete_many.return_value = 1

        with patch("wks.api.config.WKSConfig.WKSConfig.load") as mock_load:
            mock_load.return_value = mock_config
            with patch("wks.api.link.cmd_prune.Database") as mock_database:
                mock_database.return_value.__enter__.return_value = mock_db
                mock_database.return_value.__exit__.return_value = None

                result = cmd_prune(remote=False)

                # Execute the generator
                for _ in result.progress_callback(result):
                    pass

                assert result.success is True

    def test_prune_keeps_valid_links(self, mock_config, tmp_path):
        """Test that prune keeps links to existing files."""
        import platform

        from wks.api.link.cmd_prune import cmd_prune

        current_host = platform.node().split(".")[0]

        # Create existing files
        source_file = tmp_path / "source.md"
        source_file.write_text("# Source")
        target_file = tmp_path / "target.md"
        target_file.write_text("# Target")

        source_uri = f"file://{current_host}{source_file}"
        target_uri = f"file://{current_host}{target_file}"

        mock_db = MagicMock()
        mock_db.find.side_effect = [
            [{"from_uri": source_uri}],
            [{"to_uri": target_uri}],
        ]
        mock_db.delete_many.return_value = 0

        with patch("wks.api.config.WKSConfig.WKSConfig.load") as mock_load:
            mock_load.return_value = mock_config
            with patch("wks.api.link.cmd_prune.Database") as mock_database:
                mock_database.return_value.__enter__.return_value = mock_db
                mock_database.return_value.__exit__.return_value = None

                result = cmd_prune(remote=False)

                # Execute the generator
                for _ in result.progress_callback(result):
                    pass

                assert result.success is True
                assert result.output["deleted_count"] == 0

    def test_prune_with_remote_flag(self, mock_config):
        """Test that --remote flag is accepted (even if not fully implemented)."""
        from wks.api.link.cmd_prune import cmd_prune

        mock_db = MagicMock()
        mock_db.find.side_effect = [[], []]
        mock_db.delete_many.return_value = 0

        with patch("wks.api.config.WKSConfig.WKSConfig.load") as mock_load:
            mock_load.return_value = mock_config
            with patch("wks.api.link.cmd_prune.Database") as mock_database:
                mock_database.return_value.__enter__.return_value = mock_db
                mock_database.return_value.__exit__.return_value = None

                # Should not raise even with remote=True
                result = cmd_prune(remote=True)

                for _ in result.progress_callback(result):
                    pass

                assert result.success is True

    def test_prune_ignores_vault_uris(self, mock_config):
        """Test that prune handles vault:/// URIs correctly."""
        from wks.api.link.cmd_prune import cmd_prune

        # vault:/// URIs should not be checked with file existence
        vault_uri = "vault:///Notes/test.md"

        mock_db = MagicMock()
        mock_db.find.side_effect = [
            [{"from_uri": vault_uri}],
            [{"to_uri": vault_uri}],
        ]
        mock_db.delete_many.return_value = 0

        with patch("wks.api.config.WKSConfig.WKSConfig.load") as mock_load:
            mock_load.return_value = mock_config
            with patch("wks.api.link.cmd_prune.Database") as mock_database:
                mock_database.return_value.__enter__.return_value = mock_db
                mock_database.return_value.__exit__.return_value = None

                result = cmd_prune(remote=False)

                # Should complete without errors
                for _ in result.progress_callback(result):
                    pass

                assert result.success is True

    def test_prune_ignores_https_urls_without_remote(self, mock_config):
        """Test that prune ignores HTTPS URLs when remote=False."""
        from wks.api.link.cmd_prune import cmd_prune

        https_uri = "https://example.com/page"

        mock_db = MagicMock()
        mock_db.find.side_effect = [
            [],
            [{"to_uri": https_uri}],
        ]
        mock_db.delete_many.return_value = 0

        with patch("wks.api.config.WKSConfig.WKSConfig.load") as mock_load:
            mock_load.return_value = mock_config
            with patch("wks.api.link.cmd_prune.Database") as mock_database:
                mock_database.return_value.__enter__.return_value = mock_db
                mock_database.return_value.__exit__.return_value = None

                result = cmd_prune(remote=False)

                for _ in result.progress_callback(result):
                    pass

                # HTTPS should be kept (not deleted) since remote=False
                assert result.success is True
                assert result.output["stale_files"] == 0
