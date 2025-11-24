"""Tests for VaultController and fix_symlinks operation."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from wks.vault.controller import VaultController, SymlinkFixResult
from wks.vault.obsidian import ObsidianVault


class TestVaultController:
    """Test VaultController methods."""

    def test_init_default_machine_name(self):
        """Controller initializes with platform machine name."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault)
        assert controller.vault == vault
        assert isinstance(controller.machine, str)
        assert len(controller.machine) > 0

    def test_init_custom_machine_name(self):
        """Controller initializes with custom machine name."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault, machine_name="test-machine")
        assert controller.machine == "test-machine"


class TestInferTargetPath:
    """Test _infer_target_path() method."""

    def test_machine_prefixed_path(self):
        """Infer path with machine prefix."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault, machine_name="mbp")

        target = controller._infer_target_path("mbp/Users/test/file.txt")
        assert target == Path("/Users/test/file.txt")

    def test_machine_prefixed_home_relative(self):
        """Infer path relative to home when Users/ is not provided."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault, machine_name="mbp")

        target = controller._infer_target_path("mbp/2025-WKS/README.md")
        assert target == Path("/") / Path.home().relative_to(Path("/")) / "2025-WKS/README.md"

    def test_machine_prefixed_pictures_relative(self):
        """Infer Pictures path relative to home."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault, machine_name="mbp")

        target = controller._infer_target_path("mbp/Pictures/Logos/image.png")
        assert target == Path("/") / Path.home().relative_to(Path("/")) / "Pictures/Logos/image.png"


    def test_rejects_non_machine_prefix(self):
        """Reject paths that do not start with the machine name."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault, machine_name="mbp")

        target = controller._infer_target_path("other_machine/Users/test/file.txt")
        assert target is None

    def test_requires_path_after_machine(self):
        """Machine prefix alone is not enough."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault, machine_name="mbp")

        target = controller._infer_target_path("mbp")
        assert target is None

    def test_empty_path(self):
        """Empty path returns None."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault, machine_name="mbp")

        target = controller._infer_target_path("")
        assert target is None


class TestCreateSymlink:
    """Test _create_symlink() method."""

    def test_target_not_exists(self, tmp_path):
        """Target doesn't exist, return error."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault)

        symlink_path = tmp_path / "link"
        target_path = tmp_path / "missing"

        success, error = controller._create_symlink("test/path", symlink_path, target_path)

        assert success is False
        assert "Target not found" in error

    def test_create_symlink_success(self, tmp_path):
        """Successfully create symlink."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault)

        # Create target file
        target_path = tmp_path / "target.txt"
        target_path.write_text("content")

        symlink_path = tmp_path / "links" / "file.txt"

        success, error = controller._create_symlink("test/path", symlink_path, target_path)

        assert success is True
        assert error is None
        assert symlink_path.exists()
        assert symlink_path.is_symlink()
        assert symlink_path.resolve() == target_path

    def test_create_symlink_with_nested_dirs(self, tmp_path):
        """Create symlink with nested parent directories."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault)

        target_path = tmp_path / "target.txt"
        target_path.write_text("content")

        symlink_path = tmp_path / "a" / "b" / "c" / "link.txt"

        success, error = controller._create_symlink("test/path", symlink_path, target_path)

        assert success is True
        assert symlink_path.exists()
        assert symlink_path.parent.exists()


class TestCollectMissingLinks:
    """Test _collect_missing_links() method."""

    def test_no_markdown_files(self, tmp_path):
        """No markdown files in vault."""
        vault = Mock(spec=ObsidianVault)
        vault.iter_markdown_files = Mock(return_value=[])

        controller = VaultController(vault)
        links, notes_scanned = controller._collect_missing_links()

        assert len(links) == 0
        assert notes_scanned == 0

    def test_no_links_references(self, tmp_path):
        """Markdown file with no _links/ references."""
        note_path = tmp_path / "note.md"
        note_path.write_text("# Test\nNo links here")

        vault = Mock(spec=ObsidianVault)
        vault.iter_markdown_files = Mock(return_value=[note_path])
        vault.links_dir = tmp_path / "_links"

        controller = VaultController(vault)
        links, notes_scanned = controller._collect_missing_links()

        assert len(links) == 0
        assert notes_scanned == 1

    def test_existing_symlink_not_collected(self, tmp_path):
        """Existing symlink not added to collection."""
        # Create markdown with link
        note_path = tmp_path / "note.md"
        note_path.write_text("[[_links/test/file.txt]]")

        # Create the symlink (already exists)
        links_dir = tmp_path / "_links"
        symlink_path = links_dir / "test" / "file.txt"
        symlink_path.parent.mkdir(parents=True)
        symlink_path.touch()

        vault = Mock(spec=ObsidianVault)
        vault.iter_markdown_files = Mock(return_value=[note_path])
        vault.links_dir = links_dir

        with patch("wks.vault.controller.Path.home", return_value=tmp_path / "home"):
            controller = VaultController(vault, machine_name="mbp")

            home_rel = (tmp_path / "home").relative_to(Path("/"))
            existing_symlink = links_dir / f"mbp/{home_rel}/test/file.txt"
            existing_symlink.parent.mkdir(parents=True, exist_ok=True)
            existing_symlink.touch()

            links, notes_scanned = controller._collect_missing_links()

        assert len(links) == 0
        assert notes_scanned == 1

    def test_missing_symlink_collected(self, tmp_path):
        """Missing symlink added to collection."""
        note_path = tmp_path / "note.md"
        note_path.write_text("[[_links/test/missing.txt]]")

        links_dir = tmp_path / "_links"
        vault = Mock(spec=ObsidianVault)
        vault.iter_markdown_files = Mock(return_value=[note_path])
        vault.links_dir = links_dir

        with patch("wks.vault.controller.Path.home", return_value=tmp_path / "home"):
            controller = VaultController(vault, machine_name="mbp")
            links, notes_scanned = controller._collect_missing_links()

        assert len(links) == 1
        assert notes_scanned == 1
        rel_path, symlink_path = list(links)[0]
        home_rel = (tmp_path / "home").relative_to(Path("/"))
        assert rel_path == f"mbp/{home_rel}/test/missing.txt"
        assert symlink_path == links_dir / f"mbp/{home_rel}/test/missing.txt"

    def test_multiple_notes_multiple_links(self, tmp_path):
        """Multiple notes with multiple links."""
        note1 = tmp_path / "note1.md"
        note1.write_text("[[_links/test/file1.txt]]\n[[_links/test/file2.txt]]")

        note2 = tmp_path / "note2.md"
        note2.write_text("[[_links/test/file3.txt]]")

        links_dir = tmp_path / "_links"
        vault = Mock(spec=ObsidianVault)
        vault.iter_markdown_files = Mock(return_value=[note1, note2])
        vault.links_dir = links_dir

        controller = VaultController(vault)
        links, notes_scanned = controller._collect_missing_links()

        assert len(links) == 3
        assert notes_scanned == 2


class TestFixSymlinks:
    """Integration tests for fix_symlinks() method."""

    def test_no_missing_links(self, tmp_path):
        """No missing links, return empty result."""
        vault = Mock(spec=ObsidianVault)
        vault.iter_markdown_files = Mock(return_value=[])

        controller = VaultController(vault)
        result = controller.fix_symlinks()

        assert isinstance(result, SymlinkFixResult)
        assert result.notes_scanned == 0
        assert result.links_found == 0
        assert result.created == 0
        assert len(result.failed) == 0

    def test_create_symlinks_success(self, tmp_path):
        """Successfully create missing symlinks."""
        # Create target file
        target_dir = tmp_path / "targets"
        target_dir.mkdir()
        target_file = target_dir / "file.txt"
        target_file.write_text("content")

        # Create markdown with link
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        note = vault_dir / "note.md"
        note.write_text(f"[[_links/mbp{target_file}]]")

        links_dir = vault_dir / "_links"

        vault = Mock(spec=ObsidianVault)
        vault.iter_markdown_files = Mock(return_value=[note])
        vault.links_dir = links_dir

        with patch("wks.vault.controller.Path.home", return_value=tmp_path / "home"):
            controller = VaultController(vault, machine_name="mbp")
            result = controller.fix_symlinks()

        assert result.notes_scanned == 1
        assert result.links_found == 1
        assert result.created == 1
        assert len(result.failed) == 0

        # Verify symlink was created
        symlink = links_dir / f"mbp{target_file}"
        assert symlink.exists()
        assert symlink.is_symlink()

    def test_missing_target_fails(self, tmp_path):
        """Missing target file causes failure."""
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        note = vault_dir / "note.md"
        note.write_text("[[_links/mbp/missing/file.txt]]")

        links_dir = vault_dir / "_links"

        vault = Mock(spec=ObsidianVault)
        vault.iter_markdown_files = Mock(return_value=[note])
        vault.links_dir = links_dir

        controller = VaultController(vault, machine_name="mbp")
        result = controller.fix_symlinks()

        assert result.notes_scanned == 1
        assert result.links_found == 1
        assert result.created == 0
        assert len(result.failed) == 1
        assert "Target not found" in result.failed[0][1]

    def test_unknown_format_fails(self, tmp_path):
        """Unknown path format causes failure."""
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        note = vault_dir / "note.md"
        note.write_text("[[_links/unknown/format/file.txt]]")

        links_dir = vault_dir / "_links"

        vault = Mock(spec=ObsidianVault)
        vault.iter_markdown_files = Mock(return_value=[note])
        vault.links_dir = links_dir

        controller = VaultController(vault, machine_name="mbp")
        result = controller.fix_symlinks()

        assert result.notes_scanned == 1
        assert result.links_found == 1
        assert result.created == 0
        assert len(result.failed) == 1
        assert "Target not found" in result.failed[0][1]

    def test_mixed_success_and_failure(self, tmp_path):
        """Some links succeed, some fail."""
        # Create one valid target
        target_file = tmp_path / "valid.txt"
        target_file.write_text("content")

        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        note = vault_dir / "note.md"
        note.write_text(f"[[_links/mbp{target_file}]]\n[[_links/mbp/missing.txt]]")

        links_dir = vault_dir / "_links"

        vault = Mock(spec=ObsidianVault)
        vault.iter_markdown_files = Mock(return_value=[note])
        vault.links_dir = links_dir

        controller = VaultController(vault, machine_name="mbp")
        result = controller.fix_symlinks()

        assert result.notes_scanned == 1
        assert result.links_found == 2
        assert result.created == 1
        assert len(result.failed) == 1

    def test_normalizes_links_without_machine_prefix(self, tmp_path):
        """Links that skip the machine prefix are normalized and fixed."""
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        note = vault_dir / "note.md"
        note.write_text("[[_links/Pictures/2025-Test/image.png]]")

        links_dir = vault_dir / "_links"

        vault = Mock(spec=ObsidianVault)
        vault.iter_markdown_files = Mock(return_value=[note])
        vault.links_dir = links_dir
        vault.machine = "mbp"

        with patch("wks.vault.controller.Path.home", return_value=tmp_path / "home"):
            target_file = tmp_path / "home" / "Pictures/2025-Test/image.png"
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text("content")

            controller = VaultController(vault, machine_name="mbp")
            result = controller.fix_symlinks()

        assert result.notes_scanned == 1
        assert result.links_found == 1
        assert result.created == 1
        assert len(result.failed) == 0

        # Symlink created under machine namespace
        home_rel = (tmp_path / "home").relative_to(Path("/"))
        symlink_path = links_dir / f"mbp/{home_rel}/Pictures/2025-Test/image.png"
        assert symlink_path.exists()
        assert symlink_path.is_symlink()

        # Note rewritten to include machine prefix
        content = note.read_text()
        assert f"[[_links/mbp/{home_rel}/Pictures/2025-Test/image.png]]" in content


class TestMarkReferenceDeleted:
    """Ensure deletion markers are not written to content."""

    def test_mark_reference_deleted_noop(self, tmp_path):
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        links_dir = vault_dir / "_links" / "lap" / "Users" / "ww5" / "Pictures"
        links_dir.mkdir(parents=True, exist_ok=True)
        target = links_dir / "171-Santorini_Harbor.md"
        target.write_text("Original content")

        vault = ObsidianVault(vault_dir, base_dir="WKS")
        vault.mark_reference_deleted(target)

        assert target.read_text() == "Original content"
