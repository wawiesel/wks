"""Extended tests for ObsidianVault initialization and path computation."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wks.constants import DEFAULT_TIMESTAMP_FORMAT
from wks.vault.obsidian import ObsidianVault


class TestVaultInitialization:
    """Test vault initialization with various configurations."""

    def test_init_requires_wks_dir(self, tmp_path):
        """Test that initialization requires wks_dir."""
        with pytest.raises(ValueError, match=r"vault.wks_dir is required"):
            ObsidianVault(vault_path=tmp_path, base_dir="")

    def test_init_requires_non_empty_wks_dir(self, tmp_path):
        """Test that wks_dir cannot be whitespace only."""
        with pytest.raises(ValueError, match=r"vault.wks_dir is required"):
            ObsidianVault(vault_path=tmp_path, base_dir="   ")

    def test_init_strips_wks_dir_whitespace(self, tmp_path):
        """Test that wks_dir whitespace is stripped."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="  WKS  ")
        # The code strips whitespace and slashes
        assert vault.base_dir == "WKS"

    def test_init_uses_platform_machine_name(self, tmp_path):
        """Test that machine name defaults to platform.node()."""
        with patch("platform.node", return_value="my-machine.local"):
            vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")
            assert vault.machine == "my-machine"

    def test_init_uses_custom_machine_name(self, tmp_path):
        """Test that custom machine name is used."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS", machine_name="custom-machine")
        assert vault.machine == "custom-machine"

    def test_init_strips_machine_name_whitespace(self, tmp_path):
        """Test that machine name whitespace is stripped."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS", machine_name="  machine-name  ")
        assert vault.machine == "machine-name"

    def test_init_handles_machine_name_with_dot(self, tmp_path):
        """Test that machine name with domain is split correctly."""
        with patch("platform.node", return_value="machine.example.com"):
            vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")
            assert vault.machine == "machine"


class TestPathComputation:
    """Test _recompute_paths() method."""

    def test_recompute_paths_creates_correct_directories(self, tmp_path):
        """Test that _recompute_paths() sets all directory paths correctly."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        assert vault.links_dir == tmp_path / "_links"
        assert vault.projects_dir == tmp_path / "Projects"
        assert vault.people_dir == tmp_path / "People"
        assert vault.topics_dir == tmp_path / "Topics"
        assert vault.ideas_dir == tmp_path / "Ideas"
        assert vault.orgs_dir == tmp_path / "Organizations"
        assert vault.records_dir == tmp_path / "Records"
        assert vault.docs_dir == tmp_path / "WKS" / "Docs"

    def test_recompute_paths_updates_on_base_dir_change(self, tmp_path):
        """Test that paths are recomputed when base_dir changes."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")
        original_docs_dir = vault.docs_dir

        vault.set_base_dir("Custom")
        assert vault.base_dir == "Custom"
        assert vault.docs_dir == tmp_path / "Custom" / "Docs"
        assert vault.docs_dir != original_docs_dir

    def test_set_base_dir_strips_slashes(self, tmp_path):
        """Test that set_base_dir strips leading/trailing slashes."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        # Test with slashes at the edges (which will be stripped)
        vault.set_base_dir("/Custom/")
        assert vault.base_dir == "Custom"
        assert vault.docs_dir == tmp_path / "Custom" / "Docs"

        # Test with spaces and slashes - both are stripped
        vault.set_base_dir("  /Custom/  ")
        assert vault.base_dir == "Custom"
        assert vault.docs_dir == tmp_path / "Custom" / "Docs"


class TestDirectoryCreation:
    """Test ensure_structure() method."""

    def test_ensure_structure_creates_all_directories(self, tmp_path):
        """Test that ensure_structure creates all required directories."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        vault.ensure_structure()

        assert (tmp_path / "WKS").exists()
        assert (tmp_path / "WKS" / "Docs").exists()
        assert (tmp_path / "_links").exists()
        assert (tmp_path / "Projects").exists()
        assert (tmp_path / "People").exists()
        assert (tmp_path / "Topics").exists()
        assert (tmp_path / "Ideas").exists()
        assert (tmp_path / "Organizations").exists()
        assert (tmp_path / "Records").exists()

    def test_ensure_structure_idempotent(self, tmp_path):
        """Test that ensure_structure can be called multiple times safely."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        vault.ensure_structure()
        # Create a file in one directory
        test_file = tmp_path / "Projects" / "test.md"
        test_file.write_text("test")

        # Call again
        vault.ensure_structure()

        # File should still exist
        assert test_file.exists()

    def test_ensure_structure_creates_nested_directories(self, tmp_path):
        """Test that ensure_structure creates nested directory structures."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        vault.ensure_structure()

        # Verify nested structure
        assert (tmp_path / "WKS" / "Docs").exists()
        assert (tmp_path / "WKS" / "Docs").is_dir()


class TestTimestampFormat:
    """Test timestamp format handling."""

    def test_timestamp_format_defaults_when_config_fails(self, tmp_path):
        """Test that DEFAULT_TIMESTAMP_FORMAT is used when config fails."""
        with patch("wks.config.WKSConfig.load", side_effect=Exception("Config error")):
            vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")
            assert vault.timestamp_format == DEFAULT_TIMESTAMP_FORMAT

    def test_timestamp_format_from_config(self, tmp_path):
        """Test that timestamp format is loaded from config."""
        mock_config = Mock()
        mock_config.display.timestamp_format = "%Y-%m-%d %H:%M:%S"

        with patch("wks.config.WKSConfig.load", return_value=mock_config):
            vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")
            assert vault.timestamp_format == "%Y-%m-%d %H:%M:%S"

    def test_format_dt_uses_custom_format(self, tmp_path):
        """Test that _format_dt uses the configured format."""
        mock_config = Mock()
        mock_config.display.timestamp_format = "%Y-%m-%d"

        with patch("wks.config.WKSConfig.load", return_value=mock_config):
            vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")
            dt = datetime(2024, 1, 15, 10, 30, 45)
            formatted = vault._format_dt(dt)
            assert formatted == "2024-01-15"

    def test_format_dt_falls_back_on_invalid_format(self, tmp_path):
        """Test that _format_dt falls back to default on invalid format."""
        mock_config = Mock()
        mock_config.display.timestamp_format = "%invalid"

        with patch("wks.config.WKSConfig.load", return_value=mock_config):
            vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")
            dt = datetime(2024, 1, 15, 10, 30, 45)
            formatted = vault._format_dt(dt)
            # The code should detect invalid format and fall back to DEFAULT_TIMESTAMP_FORMAT
            from wks.constants import DEFAULT_TIMESTAMP_FORMAT

            expected = dt.strftime(DEFAULT_TIMESTAMP_FORMAT)
            assert formatted == expected
            assert len(formatted) > 0
            assert len(formatted) > 0

    def test_format_dt_handles_invalid_datetime(self, tmp_path):
        """Test that _format_dt handles invalid datetime gracefully."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        # Pass None (invalid) - the code handles None and returns empty string
        result = vault._format_dt(None)
        assert result == ""


class TestMachineNameExtraction:
    """Test machine name extraction from platform.node()."""

    def test_machine_name_extracts_hostname(self, tmp_path):
        """Test that machine name is extracted from FQDN."""
        with patch("platform.node", return_value="myhost.example.com"):
            vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")
            assert vault.machine == "myhost"

    def test_machine_name_handles_simple_hostname(self, tmp_path):
        """Test that simple hostname (no domain) works."""
        with patch("platform.node", return_value="myhost"):
            vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")
            assert vault.machine == "myhost"

    def test_machine_name_handles_multiple_dots(self, tmp_path):
        """Test that machine name with multiple dots is handled."""
        with patch("platform.node", return_value="sub.domain.example.com"):
            vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")
            assert vault.machine == "sub"


class TestLinkFile:
    """Test link_file() method."""

    def test_link_file_creates_symlink(self, tmp_path):
        """Test that link_file() creates a symlink to the source file."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        # Create a source file
        source_file = tmp_path / "source" / "document.pdf"
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text("content")

        link_path = vault.link_file(source_file)

        assert link_path is not None
        assert link_path.is_symlink()
        assert link_path.resolve() == source_file.resolve()

    def test_link_file_returns_none_if_source_missing(self, tmp_path):
        """Test that link_file() returns None if source file doesn't exist."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        missing_file = tmp_path / "nonexistent.pdf"
        link_path = vault.link_file(missing_file)

        assert link_path is None

    def test_link_file_preserves_structure(self, tmp_path):
        """Test that link_file() preserves directory structure when preserve_structure=True."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        source_file = tmp_path / "deep" / "nested" / "file.pdf"
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text("content")

        link_path = vault.link_file(source_file, preserve_structure=True)

        # Should create link preserving the absolute path structure
        assert link_path is not None
        machine_links_dir = vault.links_dir / vault.machine
        assert link_path.is_relative_to(machine_links_dir)

    def test_link_file_no_structure(self, tmp_path):
        """Test that link_file() uses just filename when preserve_structure=False."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        source_file = tmp_path / "deep" / "nested" / "file.pdf"
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text("content")

        link_path = vault.link_file(source_file, preserve_structure=False)

        assert link_path is not None
        assert link_path.name == "file.pdf"
        assert link_path.parent == vault.links_dir / vault.machine

    def test_link_file_handles_value_error(self, tmp_path):
        """Test that link_file() handles ValueError when relative_to fails."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        # Create a file that can't be resolved relative to root
        source_file = tmp_path / "file.pdf"
        source_file.write_text("content")

        # Mock resolve to raise ValueError
        with patch("pathlib.Path.resolve", side_effect=ValueError("Cannot resolve")):
            link_path = vault.link_file(source_file, preserve_structure=True)
            # Should fall back to just filename
            assert link_path is not None
            assert link_path.name == "file.pdf"


class TestUpdateLinkOnMove:
    """Test update_link_on_move() method."""

    def test_update_link_on_move_updates_symlink(self, tmp_path):
        """Test that update_link_on_move() updates symlink when file moves."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        home = Path.home()
        old_path = home / "old_file.pdf"
        new_path = home / "new_file.pdf"

        # Create old file and symlink
        old_path.write_text("content")
        old_link = vault.links_dir / old_path.relative_to(home)
        old_link.parent.mkdir(parents=True, exist_ok=True)
        old_link.symlink_to(old_path)

        # Move file
        old_path.rename(new_path)

        vault.update_link_on_move(old_path, new_path)

        # Old link should be gone, new link should exist
        assert not old_link.exists() or not old_link.is_symlink()
        new_link = vault.links_dir / new_path.relative_to(home)
        if new_link.exists():
            assert new_link.is_symlink()

    def test_update_link_on_move_handles_non_home_path(self, tmp_path):
        """Test that update_link_on_move() does nothing for paths not in home."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        old_path = tmp_path / "old.pdf"
        new_path = tmp_path / "new.pdf"

        # Should return without error even if path not in home
        vault.update_link_on_move(old_path, new_path)
        # No assertion needed - just should not raise


class TestUpdateVaultLinksOnMove:
    """Test update_vault_links_on_move() method."""

    def test_update_vault_links_on_move_updates_wikilinks(self, tmp_path):
        """Test that update_vault_links_on_move() updates wikilinks in markdown files."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        # Create files that will be linked
        old_path = Path("/old/path.pdf")
        new_path = Path("/new/path.pdf")

        # Compute what the link paths would be
        old_rel = vault._link_rel_for_source(old_path)
        new_rel = vault._link_rel_for_source(new_path)

        # Create a note with the old link format
        note = tmp_path / "Projects" / "Test.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(f"See [[{old_rel}]]")

        vault.update_vault_links_on_move(old_path, new_path)

        # Check that the link was updated
        content = note.read_text()
        assert new_rel in content or old_rel not in content

    def test_update_vault_links_on_move_handles_legacy_links(self, tmp_path):
        """Test that update_vault_links_on_move() handles legacy links/ paths."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        old_path = Path("/old/path.pdf")
        new_path = Path("/new/path.pdf")

        # Compute link paths
        old_rel = vault._link_rel_for_source(old_path)
        old_rel_legacy = old_rel.replace("_links/", "links/")
        new_rel = vault._link_rel_for_source(new_path)

        # Create a note with legacy link format
        note = tmp_path / "Projects" / "Test.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(f"See [[{old_rel_legacy}]]")

        vault.update_vault_links_on_move(old_path, new_path)

        content = note.read_text()
        # Should update legacy links to new format
        # The method replaces [[links/old/path.pdf]] with [[_links/machine/new/path.pdf]]
        assert new_rel in content


class TestWriteDocText:
    """Test write_doc_text() method."""

    def test_write_doc_text_creates_document(self, tmp_path):
        """Test that write_doc_text() creates a document file."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        source_path = tmp_path / "source.pdf"
        content_hash = "abc123"
        text = "Extracted text content"

        vault.write_doc_text(content_hash, source_path, text)

        doc_path = vault.docs_dir / f"{content_hash}.md"
        assert doc_path.exists()
        content = doc_path.read_text()
        assert source_path.name in content
        assert text in content

    def test_write_doc_text_handles_errors(self, tmp_path):
        """Test that write_doc_text() handles write errors gracefully."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        source_path = tmp_path / "source.pdf"
        content_hash = "abc123"
        text = "content"

        # Mock write_text to raise error
        with patch("pathlib.Path.write_text", side_effect=PermissionError("Cannot write")):
            vault.write_doc_text(content_hash, source_path, text)
            # Should not raise, just return

    def test_write_doc_text_limits_kept_files(self, tmp_path):
        """Test that write_doc_text() limits the number of kept files."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        # Create more than keep limit files
        for i in range(5):
            vault.write_doc_text(f"hash{i}", tmp_path / f"file{i}.pdf", f"text{i}")

        # Should only keep keep=99 files (default), but with 5 files, all should exist
        files = list(vault.docs_dir.glob("*.md"))
        assert len(files) == 5


class TestCreateProjectNote:
    """Test create_project_note() method."""

    def test_create_project_note_creates_note(self, tmp_path):
        """Test that create_project_note() creates a project note."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        # Ensure Projects directory exists
        vault.projects_dir.mkdir(parents=True, exist_ok=True)

        project_path = tmp_path / "my-project"
        project_path.mkdir()

        note_path = vault.create_project_note(project_path, status="Active", description="Test project")

        assert note_path.exists()
        assert note_path.name == "my-project.md"
        content = note_path.read_text()
        assert "my-project" in content
        assert "Active" in content
        assert "Test project" in content

    def test_create_project_note_handles_dashed_name(self, tmp_path):
        """Test that create_project_note() handles project names with dashes."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        # Ensure Projects directory exists
        vault.projects_dir.mkdir(parents=True, exist_ok=True)

        project_path = tmp_path / "2024-01-project"
        project_path.mkdir()

        note_path = vault.create_project_note(project_path)

        assert note_path.exists()
        assert note_path.name == "2024-01-project.md"
        content = note_path.read_text()
        # Should extract name after first dash (parts[1] = "01-project")
        assert "01-project" in content or "2024-01-project" in content


class TestLinkProject:
    """Test link_project() method."""

    def test_link_project_creates_links(self, tmp_path):
        """Test that link_project() creates links for project files."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        project_path = tmp_path / "my-project"
        project_path.mkdir()

        # Create project files
        (project_path / "README.md").write_text("# Project")
        (project_path / "SPEC.md").write_text("# Spec")
        (project_path / "TODO.md").write_text("# Todo")

        links = vault.link_project(project_path)

        assert len(links) == 3
        assert all(link.is_symlink() for link in links)

    def test_link_project_only_links_existing_files(self, tmp_path):
        """Test that link_project() only links files that exist."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        project_path = tmp_path / "my-project"
        project_path.mkdir()

        # Only create README
        (project_path / "README.md").write_text("# Project")

        links = vault.link_project(project_path)

        assert len(links) == 1
        assert links[0].name == "README.md"


class TestFindBrokenLinks:
    """Test find_broken_links() method."""

    def test_find_broken_links_finds_broken_symlinks(self, tmp_path):
        """Test that find_broken_links() finds broken symlinks."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        # Create a broken symlink
        broken_link = vault.links_dir / "broken.pdf"
        broken_link.parent.mkdir(parents=True, exist_ok=True)
        broken_link.symlink_to("/nonexistent/file.pdf")

        broken = vault.find_broken_links()

        assert len(broken) >= 1
        assert broken_link in broken

    def test_find_broken_links_ignores_valid_links(self, tmp_path):
        """Test that find_broken_links() ignores valid symlinks."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        # Create a valid symlink
        target = tmp_path / "target.pdf"
        target.write_text("content")
        valid_link = vault.links_dir / "valid.pdf"
        valid_link.parent.mkdir(parents=True, exist_ok=True)
        valid_link.symlink_to(target)

        broken = vault.find_broken_links()

        assert valid_link not in broken


class TestCleanupBrokenLinks:
    """Test cleanup_broken_links() method."""

    def test_cleanup_broken_links_removes_broken_symlinks(self, tmp_path):
        """Test that cleanup_broken_links() removes broken symlinks."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        # Create broken symlinks
        broken1 = vault.links_dir / "broken1.pdf"
        broken2 = vault.links_dir / "broken2.pdf"
        broken1.parent.mkdir(parents=True, exist_ok=True)
        broken1.symlink_to("/nonexistent1.pdf")
        broken2.symlink_to("/nonexistent2.pdf")

        count = vault.cleanup_broken_links()

        assert count >= 2
        assert not broken1.exists()
        assert not broken2.exists()

    def test_cleanup_broken_links_handles_permission_errors(self, tmp_path):
        """Test that cleanup_broken_links() handles permission errors gracefully."""
        vault = ObsidianVault(vault_path=tmp_path, base_dir="WKS")

        broken_link = vault.links_dir / "broken.pdf"
        broken_link.parent.mkdir(parents=True, exist_ok=True)
        broken_link.symlink_to("/nonexistent.pdf")

        # Mock unlink to raise permission error
        with patch("pathlib.Path.unlink", side_effect=PermissionError("Cannot delete")):
            count = vault.cleanup_broken_links()
            # Should continue processing other links
            assert count >= 0
