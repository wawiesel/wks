"""Tests for VaultController fix_symlinks operation."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from pymongo.collection import Collection

from wks.vault.controller import VaultController, SymlinkFixResult
from wks.vault.obsidian import ObsidianVault


@pytest.fixture
def vault_root(tmp_path):
    """Create a temporary vault structure."""
    root = tmp_path / "vault"
    (root / "_links").mkdir(parents=True, exist_ok=True)
    (root / "WKS").mkdir(exist_ok=True)
    return root


@pytest.fixture
def vault(vault_root):
    """Create an ObsidianVault instance."""
    return ObsidianVault(
        vault_path=vault_root,
        base_dir="WKS",
        machine_name="test-machine"
    )


@pytest.fixture
def controller(vault):
    """Create a VaultController instance."""
    return VaultController(vault, machine_name="test-machine")


@pytest.fixture
def mock_mongo_collection():
    """Mock MongoDB collection with file:// links."""
    collection = MagicMock(spec=Collection)
    
    # Mock cursor with file:// URIs
    mock_cursor = [
        {"to_uri": "file:///Users/test/file1.pdf"},
        {"to_uri": "file:///Users/test/file2.pdf"},
        {"to_uri": "file:///Users/test/subdir/file3.pdf"},
        {"to_uri": "vault:///SomeNote"},  # Should be filtered out
    ]
    collection.find.return_value = mock_cursor
    return collection


@pytest.fixture
def mock_mongo_client(mock_mongo_collection):
    """Mock MongoDB client."""
    client = MagicMock()
    client.__getitem__.return_value.__getitem__.return_value = mock_mongo_collection
    return client


class TestFixSymlinks:
    """Test fix_symlinks() operation end-to-end."""

    def test_fix_symlinks_creates_symlinks(self, controller, vault_root, tmp_path, mock_mongo_client):
        """Test that fix_symlinks creates symlinks for file:// URIs."""
        # Create target files
        target1 = tmp_path / "file1.pdf"
        target1.write_text("content1")
        target2 = tmp_path / "file2.pdf"
        target2.write_text("content2")
        target3 = tmp_path / "subdir" / "file3.pdf"
        target3.parent.mkdir(exist_ok=True)
        target3.write_text("content3")

        # Mock WKSConfig and MongoClient
        mock_config = Mock()
        mock_config.mongo.uri = "mongodb://localhost:27017"
        mock_config.vault.database = "test_db.test_coll"

        with patch("wks.vault.controller.WKSConfig.load", return_value=mock_config):
            with patch("wks.vault.controller.MongoClient", return_value=mock_mongo_client):
                # Update mock to return correct paths
                mock_cursor = [
                    {"to_uri": f"file://{target1}"},
                    {"to_uri": f"file://{target2}"},
                    {"to_uri": f"file://{target3}"},
                ]
                mock_mongo_client.__getitem__.return_value.__getitem__.return_value.find.return_value = mock_cursor
                
                result = controller.fix_symlinks()

        # Verify results
        assert result.links_found == 3
        assert result.created == 3
        assert len(result.failed) == 0

        # Verify symlinks were created
        machine_links_dir = vault_root / "_links" / "test-machine"
        assert (machine_links_dir / "Users" / "test" / "file1.pdf").is_symlink()
        assert (machine_links_dir / "Users" / "test" / "file2.pdf").is_symlink()
        assert (machine_links_dir / "Users" / "test" / "subdir" / "file3.pdf").is_symlink()

    def test_fix_symlinks_deletes_existing_directory(self, controller, vault_root, mock_mongo_client):
        """Test that fix_symlinks deletes existing _links/<machine>/ directory."""
        machine_links_dir = vault_root / "_links" / "test-machine"
        old_file = machine_links_dir / "old_file.pdf"
        old_file.parent.mkdir(parents=True, exist_ok=True)
        old_file.write_text("old content")

        mock_config = Mock()
        mock_config.mongo.uri = "mongodb://localhost:27017"
        mock_config.vault.database = "test_db.test_coll"

        # Mock empty cursor (no links)
        mock_mongo_client.__getitem__.return_value.__getitem__.return_value.find.return_value = []

        with patch("wks.vault.controller.WKSConfig.load", return_value=mock_config):
            with patch("wks.vault.controller.MongoClient", return_value=mock_mongo_client):
                result = controller.fix_symlinks()

        # Old file should be gone
        assert not old_file.exists()
        assert result.created == 0

    def test_fix_symlinks_handles_missing_targets(self, controller, vault_root, mock_mongo_client):
        """Test that missing target files are reported in failed list."""
        mock_config = Mock()
        mock_config.mongo.uri = "mongodb://localhost:27017"
        mock_config.vault.database = "test_db.test_coll"

        # Mock cursor with non-existent file
        mock_cursor = [
            {"to_uri": "file:///nonexistent/file.pdf"},
        ]
        mock_mongo_client.__getitem__.return_value.__getitem__.return_value.find.return_value = mock_cursor

        with patch("wks.vault.controller.WKSConfig.load", return_value=mock_config):
            with patch("wks.vault.controller.MongoClient", return_value=mock_mongo_client):
                result = controller.fix_symlinks()

        assert result.links_found == 1
        assert result.created == 0
        assert len(result.failed) == 1
        assert "Target file not found" in result.failed[0][1]

    def test_fix_symlinks_handles_permission_errors(self, controller, vault_root, tmp_path, mock_mongo_client):
        """Test error handling when symlink creation fails."""
        target = tmp_path / "file.pdf"
        target.write_text("content")

        mock_config = Mock()
        mock_config.mongo.uri = "mongodb://localhost:27017"
        mock_config.vault.database = "test_db.test_coll"

        mock_cursor = [
            {"to_uri": f"file://{target}"},
        ]
        mock_mongo_client.__getitem__.return_value.__getitem__.return_value.find.return_value = mock_cursor

        with patch("wks.vault.controller.WKSConfig.load", return_value=mock_config):
            with patch("wks.vault.controller.MongoClient", return_value=mock_mongo_client):
                # Mock symlink creation to raise PermissionError
                with patch("pathlib.Path.symlink_to", side_effect=PermissionError("Permission denied")):
                    result = controller.fix_symlinks()

        assert result.links_found == 1
        assert result.created == 0
        assert len(result.failed) == 1
        assert "Permission denied" in result.failed[0][1]

    def test_fix_symlinks_handles_config_load_error(self, controller):
        """Test error handling when config fails to load."""
        with patch("wks.vault.controller.WKSConfig.load", side_effect=Exception("Config error")):
            result = controller.fix_symlinks()

        assert result.notes_scanned == 0
        assert result.links_found == 0
        assert result.created == 0
        assert len(result.failed) == 1
        assert "config" in result.failed[0][0]
        assert "Config error" in result.failed[0][1]

    def test_fix_symlinks_handles_mongo_query_error(self, controller, mock_mongo_client):
        """Test error handling when MongoDB query fails."""
        mock_config = Mock()
        mock_config.mongo.uri = "mongodb://localhost:27017"
        mock_config.vault.database = "test_db.test_coll"

        # Mock collection.find to raise exception
        mock_mongo_client.__getitem__.return_value.__getitem__.return_value.find.side_effect = Exception("DB error")

        with patch("wks.vault.controller.WKSConfig.load", return_value=mock_config):
            with patch("wks.vault.controller.MongoClient", return_value=mock_mongo_client):
                result = controller.fix_symlinks()

        assert result.notes_scanned == 0
        assert result.links_found == 0
        assert result.created == 0
        assert len(result.failed) == 1
        assert "vault_db" in result.failed[0][0]

    def test_fix_symlinks_handles_directory_deletion_error(self, controller, vault_root, mock_mongo_client):
        """Test error handling when directory deletion fails."""
        machine_links_dir = vault_root / "_links" / "test-machine"
        machine_links_dir.mkdir(parents=True, exist_ok=True)

        mock_config = Mock()
        mock_config.mongo.uri = "mongodb://localhost:27017"
        mock_config.vault.database = "test_db.test_coll"

        mock_mongo_client.__getitem__.return_value.__getitem__.return_value.find.return_value = []

        with patch("wks.vault.controller.WKSConfig.load", return_value=mock_config):
            with patch("wks.vault.controller.MongoClient", return_value=mock_mongo_client):
                # Mock shutil.rmtree to raise exception
                with patch("shutil.rmtree", side_effect=PermissionError("Cannot delete")):
                    result = controller.fix_symlinks()

        assert len(result.failed) == 1
        assert "_links/test-machine" in result.failed[0][0]
        assert "Cannot delete" in result.failed[0][1]

    def test_fix_symlinks_filters_non_file_uris(self, controller, vault_root, mock_mongo_client):
        """Test that only file:// URIs are processed."""
        mock_config = Mock()
        mock_config.mongo.uri = "mongodb://localhost:27017"
        mock_config.vault.database = "test_db.test_coll"

        # Mix of file:// and other URIs
        mock_cursor = [
            {"to_uri": "file:///Users/test/file1.pdf"},
            {"to_uri": "vault:///SomeNote"},
            {"to_uri": "https://example.com"},
            {"to_uri": "file:///Users/test/file2.pdf"},
        ]
        mock_mongo_client.__getitem__.return_value.__getitem__.return_value.find.return_value = mock_cursor

        with patch("wks.vault.controller.WKSConfig.load", return_value=mock_config):
            with patch("wks.vault.controller.MongoClient", return_value=mock_mongo_client):
                result = controller.fix_symlinks()

        # Should only process file:// URIs
        assert result.links_found == 4  # All found, but only file:// processed
        # Created count depends on whether targets exist

    def test_fix_symlinks_machine_specific_directories(self, vault_root, tmp_path, mock_mongo_client):
        """Test that symlinks are created in machine-specific directories."""
        # Create controller with different machine name
        vault = ObsidianVault(
            vault_path=vault_root,
            base_dir="WKS",
            machine_name="another-machine"
        )
        controller = VaultController(vault, machine_name="another-machine")

        target = tmp_path / "file.pdf"
        target.write_text("content")

        mock_config = Mock()
        mock_config.mongo.uri = "mongodb://localhost:27017"
        mock_config.vault.database = "test_db.test_coll"

        mock_cursor = [
            {"to_uri": f"file://{target}"},
        ]
        mock_mongo_client.__getitem__.return_value.__getitem__.return_value.find.return_value = mock_cursor

        with patch("wks.vault.controller.WKSConfig.load", return_value=mock_config):
            with patch("wks.vault.controller.MongoClient", return_value=mock_mongo_client):
                result = controller.fix_symlinks()

        # Verify symlink is in machine-specific directory
        machine_links_dir = vault_root / "_links" / "another-machine"
        assert machine_links_dir.exists()
        # Symlink path depends on target path structure
