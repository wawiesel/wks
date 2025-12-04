"""Complete tests for VaultController to achieve 100% coverage."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from wks.vault.controller import SymlinkFixResult, VaultController
from wks.vault.obsidian import ObsidianVault


@pytest.mark.integration
class TestFixSymlinks:
    """Test fix_symlinks method - lines 35-140."""

    def test_fix_symlinks_success(self, tmp_path):
        """fix_symlinks successfully rebuilds symlinks from database."""
        # Setup vault
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        links_dir = vault_dir / "_links"
        links_dir.mkdir()

        vault = Mock(spec=ObsidianVault)
        vault.links_dir = links_dir

        # Setup target file
        target_file = tmp_path / "documents" / "test.pdf"
        target_file.parent.mkdir(parents=True)
        target_file.write_text("test content")

        # Patch at import location within the method
        with patch("wks.config.WKSConfig") as mock_config_class, patch(
            "pymongo.MongoClient"
        ) as mock_mongo_class:
            # Mock config
            mock_config = Mock()
            mock_config.mongo.uri = "mongodb://localhost"
            mock_config.vault.database = "wks.vault"
            mock_config_class.load.return_value = mock_config

            # Mock MongoDB
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_mongo_class.return_value = mock_client
            mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

            # Return file:// URIs from database
            mock_collection.find.return_value = [{"to_uri": f"file://{target_file}"}]

            controller = VaultController(vault, machine_name="test-machine")
            result = controller.fix_symlinks()

            assert isinstance(result, SymlinkFixResult)
            assert result.links_found == 1
            assert result.created == 1
            assert len(result.failed) == 0

    def test_fix_symlinks_config_load_error(self, tmp_path):
        """fix_symlinks handles config load errors."""
        vault = Mock(spec=ObsidianVault)
        vault.links_dir = tmp_path / "_links"

        with patch("wks.config.WKSConfig") as mock_config_class:
            mock_config_class.load.side_effect = Exception("Config error")

            controller = VaultController(vault)
            result = controller.fix_symlinks()

            assert result.created == 0
            assert len(result.failed) > 0
            assert "config" in result.failed[0][0]
            assert "Config error" in result.failed[0][1]

    def test_fix_symlinks_db_connection_error(self, tmp_path):
        """fix_symlinks handles database connection errors."""
        vault = Mock(spec=ObsidianVault)
        vault.links_dir = tmp_path / "_links"

        with patch("wks.config.WKSConfig") as mock_config_class, patch(
            "pymongo.MongoClient"
        ) as mock_mongo_class:
            mock_config = Mock()
            mock_config.mongo.uri = "mongodb://localhost"
            mock_config.vault.database = "wks.vault"
            mock_config_class.load.return_value = mock_config

            mock_mongo_class.side_effect = Exception("Connection failed")

            controller = VaultController(vault)
            result = controller.fix_symlinks()

            assert result.created == 0
            assert len(result.failed) > 0
            assert "vault_db" in result.failed[0][0]

    def test_fix_symlinks_target_not_found(self, tmp_path):
        """fix_symlinks handles missing target files."""
        vault = Mock(spec=ObsidianVault)
        vault.links_dir = tmp_path / "_links"

        with patch("wks.config.WKSConfig") as mock_config_class, patch(
            "pymongo.MongoClient"
        ) as mock_mongo_class:
            mock_config = Mock()
            mock_config.mongo.uri = "mongodb://localhost"
            mock_config.vault.database = "wks.vault"
            mock_config_class.load.return_value = mock_config

            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_mongo_class.return_value = mock_client
            mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

            # Return URI to non-existent file
            mock_collection.find.return_value = [{"to_uri": "file:///nonexistent/file.pdf"}]

            controller = VaultController(vault)
            result = controller.fix_symlinks()

            assert result.created == 0
            assert len(result.failed) > 0
            assert "Target file not found" in result.failed[0][1]


@pytest.mark.integration
class TestValidateVault:
    """Test validate_vault method - lines 141-172."""

    def test_validate_vault_all_ok(self):
        """validate_vault returns is_valid=True when no broken links."""
        vault = Mock(spec=ObsidianVault)

        with patch("wks.vault.indexer.VaultLinkScanner") as mock_scanner_class:
            mock_scanner = Mock()
            mock_scanner.stats.notes_scanned = 10
            mock_scanner.stats.edge_total = 50

            # All records have status "ok"
            mock_records = []
            for _ in range(50):
                record = Mock()
                record.status = "ok"
                mock_records.append(record)

            mock_scanner.scan.return_value = mock_records
            mock_scanner_class.return_value = mock_scanner

            controller = VaultController(vault)
            result = controller.validate_vault()

            assert result["is_valid"] is True
            assert result["broken_count"] == 0
            assert result["notes_scanned"] == 10
            assert result["links_found"] == 50
            assert result["broken_by_status"] == {}

    def test_validate_vault_with_broken_links(self):
        """validate_vault returns broken links grouped by status."""
        vault = Mock(spec=ObsidianVault)

        with patch("wks.vault.indexer.VaultLinkScanner") as mock_scanner_class:
            mock_scanner = Mock()
            mock_scanner.stats.notes_scanned = 5
            mock_scanner.stats.edge_total = 10

            # Create mix of ok and broken records
            mock_records = []

            # 8 ok records
            for _ in range(8):
                record = Mock()
                record.status = "ok"
                mock_records.append(record)

            # 2 broken records
            for i in range(2):
                record = Mock()
                record.status = "missing_target"
                record.note_path = Path(f"note{i}.md")
                record.line_number = i + 1
                record.raw_target = f"missing{i}.md"
                mock_records.append(record)

            mock_scanner.scan.return_value = mock_records
            mock_scanner_class.return_value = mock_scanner

            controller = VaultController(vault)
            result = controller.validate_vault()

            assert result["is_valid"] is False
            assert result["broken_count"] == 2
            assert "missing_target" in result["broken_by_status"]
            assert len(result["broken_by_status"]["missing_target"]) == 2


@pytest.mark.integration
class TestSyncVault:
    """Test sync_vault static method - lines 173-189."""

    def test_sync_vault_success(self):
        """sync_vault successfully syncs vault links."""
        with (
            patch("wks.config.WKSConfig") as mock_config_class,
            patch("wks.utils.expand_path") as mock_expand,
            patch("wks.vault.obsidian.ObsidianVault"),
            patch("wks.vault.indexer.VaultLinkIndexer") as mock_indexer_class,
        ):
            # Mock config
            mock_config = Mock()
            mock_config.vault.base_dir = "/vault"
            mock_config.vault.wks_dir = "WKS"
            mock_config_class.load.return_value = mock_config

            mock_expand.return_value = Path("/vault")

            # Mock indexer result
            mock_indexer = Mock()
            mock_result = Mock()
            mock_result.stats.notes_scanned = 10
            mock_result.stats.edge_total = 50
            mock_result.sync_duration_ms = 1000
            mock_result.stats.errors = []
            mock_indexer.sync.return_value = mock_result
            mock_indexer_class.from_config.return_value = mock_indexer

            result = VaultController.sync_vault(batch_size=1000)

            assert result["notes_scanned"] == 10
            assert result["edges_written"] == 50
            assert result["sync_duration_ms"] == 1000
            assert result["errors"] == []

    def test_sync_vault_missing_base_dir(self):
        """sync_vault raises error when base_dir not configured."""
        with patch("wks.config.WKSConfig") as mock_config_class:
            mock_config = Mock()
            mock_config.vault.base_dir = ""
            mock_config.vault.wks_dir = "WKS"
            mock_config_class.load.return_value = mock_config

            with pytest.raises(ValueError, match="vault.base_dir not configured"):
                VaultController.sync_vault()


@pytest.mark.integration
class TestFixSymlinksEdgeCases:
    """Test edge cases in fix_symlinks to reach 100% coverage."""

    def test_fix_symlinks_rmtree_error(self, tmp_path):
        """fix_symlinks handles error when deleting existing directory."""
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        links_dir = vault_dir / "_links"
        machine_dir = links_dir / "test-machine"
        machine_dir.mkdir(parents=True)

        vault = Mock(spec=ObsidianVault)
        vault.links_dir = links_dir

        # Make directory undeletable by mocking shutil.rmtree to fail
        with patch("shutil.rmtree") as mock_rmtree:
            mock_rmtree.side_effect = PermissionError("Cannot delete")

            controller = VaultController(vault, machine_name="test-machine")
            result = controller.fix_symlinks()

            assert result.created == 0
            assert len(result.failed) > 0
            assert "_links/test-machine" in result.failed[0][0]
            assert "Cannot delete" in result.failed[0][1]

    def test_fix_symlinks_relative_path_error(self, tmp_path):
        """fix_symlinks handles error when creating relative path."""
        vault = Mock(spec=ObsidianVault)
        vault.links_dir = tmp_path / "_links"

        # Create a target file
        target_file = tmp_path / "test.pdf"
        target_file.write_text("content")

        with patch("wks.config.WKSConfig") as mock_config_class, patch(
            "pymongo.MongoClient"
        ) as mock_mongo_class:
            mock_config = Mock()
            mock_config.mongo.uri = "mongodb://localhost"
            mock_config.vault.database = "wks.vault"
            mock_config_class.load.return_value = mock_config

            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_mongo_class.return_value = mock_client
            mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

            mock_collection.find.return_value = [{"to_uri": f"file://{target_file}"}]

            controller = VaultController(vault)

            # Mock Path.relative_to to raise an error
            with patch.object(Path, "relative_to", side_effect=ValueError("Not relative")):
                result = controller.fix_symlinks()

                assert result.created == 0
                assert len(result.failed) > 0
                assert "Cannot create relative path" in result.failed[0][1]

    def test_fix_symlinks_symlink_creation_error(self, tmp_path):
        """fix_symlinks handles error when creating symlink."""
        vault = Mock(spec=ObsidianVault)
        vault.links_dir = tmp_path / "_links"

        # Create a target file
        target_file = tmp_path / "test.pdf"
        target_file.write_text("content")

        with patch("wks.config.WKSConfig") as mock_config_class, patch(
            "pymongo.MongoClient"
        ) as mock_mongo_class:
            mock_config = Mock()
            mock_config.mongo.uri = "mongodb://localhost"
            mock_config.vault.database = "wks.vault"
            mock_config_class.load.return_value = mock_config

            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_mongo_class.return_value = mock_client
            mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

            mock_collection.find.return_value = [{"to_uri": f"file://{target_file}"}]

            controller = VaultController(vault)

            # Mock symlink_to to raise an error
            with patch.object(Path, "symlink_to", side_effect=OSError("Symlink failed")):
                result = controller.fix_symlinks()

                assert result.created == 0
                assert len(result.failed) > 0
                assert "Failed to create symlink" in result.failed[0][1]

    def test_fix_symlinks_skips_non_file_uris(self, tmp_path):
        """fix_symlinks skips URIs that don't start with file://."""
        vault = Mock(spec=ObsidianVault)
        vault.links_dir = tmp_path / "_links"

        with patch("wks.config.WKSConfig") as mock_config_class, patch(
            "pymongo.MongoClient"
        ) as mock_mongo_class:
            mock_config = Mock()
            mock_config.mongo.uri = "mongodb://localhost"
            mock_config.vault.database = "wks.vault"
            mock_config_class.load.return_value = mock_config

            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_mongo_class.return_value = mock_client
            mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

            # Return non-file:// URIs
            mock_collection.find.return_value = [
                {"to_uri": "https://example.com"},
                {"to_uri": "vault:///note.md"},
            ]

            controller = VaultController(vault)
            result = controller.fix_symlinks()

            # Should skip both URIs
            assert result.created == 0
            assert result.links_found == 2
            assert len(result.failed) == 0
