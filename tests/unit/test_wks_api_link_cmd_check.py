"""Tests for wks.api.link.cmd_check link extraction."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wks.api.link.cmd_check import cmd_check


@pytest.fixture
def mock_config():
    """Mock configuration for tests."""
    config = MagicMock()
    config.monitor = MagicMock()
    config.vault = MagicMock()
    config.vault.base_dir = "/mock/vault"
    return config


@pytest.fixture
def temp_markdown_file(tmp_path):
    """Create a temporary markdown file with various link types."""
    file = tmp_path / "test.md"
    file.write_text("""# Test Document

[[WikiLink]]
[[WikiLink|With Alias]]
![[EmbeddedNote]]
[Named Link](https://example.com)
[Local Link](./local.md)
""")
    return file


@pytest.fixture
def temp_html_file(tmp_path):
    """Create a temporary HTML file with links."""
    file = tmp_path / "test.html"
    file.write_text("""<!DOCTYPE html>
<html>
<a href="https://example.com">Link</a>
<img src="image.png">
</html>
""")
    return file


@pytest.fixture
def temp_rst_file(tmp_path):
    """Create a temporary RST file with links."""
    file = tmp_path / "test.rst"
    file.write_text("""`Link Text <https://example.com>`_

.. image:: diagram.png
""")
    return file


@pytest.fixture
def temp_txt_file(tmp_path):
    """Create a temporary text file with URLs."""
    file = tmp_path / "test.txt"
    file.write_text("""Check out https://example.com for more info.
Also see https://another.com/page
""")
    return file


class TestCmdCheckLinkExtraction:
    """Test link extraction through cmd_check public API."""

    @patch("wks.api.link.cmd_check.WKSConfig")
    @patch("wks.api.link.cmd_check.explain_path")
    @patch("wks.api.link.cmd_check.Vault")
    def test_markdown_wikilinks_extracted(
        self, mock_vault_cls, mock_explain_path, mock_config_cls, mock_config, temp_markdown_file
    ):
        """Test WikiLinks are extracted from markdown files."""
        mock_config_cls.load.return_value = mock_config
        mock_explain_path.return_value = (True, [])
        vault_mock = MagicMock(vault_path=Path("/mock/vault"), links_dir=Path("/mock/vault/_links"))
        vault_mock.resolve_link.side_effect = lambda t: MagicMock(target_uri=t)
        mock_vault_cls.return_value.__enter__ = MagicMock(return_value=vault_mock)
        mock_vault_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = cmd_check(str(temp_markdown_file))

        # Execute the progress callback to get results
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        links = result.output["links"]

        # Should find WikiLinks
        wikilink_targets = [lnk["to_local_uri"] for lnk in links if "WikiLink" in lnk.get("to_local_uri", "")]
        assert len(wikilink_targets) >= 2  # At least [[WikiLink]] and [[WikiLink|With Alias]]

    @patch("wks.api.link.cmd_check.WKSConfig")
    @patch("wks.api.link.cmd_check.explain_path")
    @patch("wks.api.link.cmd_check.Vault")
    def test_markdown_named_link_name_captured(
        self, mock_vault_cls, mock_explain_path, mock_config_cls, mock_config, temp_markdown_file
    ):
        """Test that named links have their name/alias captured."""
        mock_config_cls.load.return_value = mock_config
        mock_explain_path.return_value = (True, [])
        vault_mock = MagicMock(vault_path=Path("/mock/vault"), links_dir=Path("/mock/vault/_links"))
        vault_mock.resolve_link.side_effect = lambda t: MagicMock(target_uri=t)
        mock_vault_cls.return_value.__enter__ = MagicMock(return_value=vault_mock)
        mock_vault_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = cmd_check(str(temp_markdown_file))
        for _ in result.progress_callback(result):
            pass

        links = result.output["links"]

        # Find the named link
        named_link = next((lnk for lnk in links if lnk.get("to_local_uri") == "https://example.com"), None)
        assert named_link is not None
        assert named_link.get("name") == "Named Link"

    @patch("wks.api.link.cmd_check.WKSConfig")
    @patch("wks.api.link.cmd_check.explain_path")
    @patch("wks.api.link.cmd_check.Vault")
    def test_html_links_extracted(
        self, mock_vault_cls, mock_explain_path, mock_config_cls, mock_config, temp_html_file
    ):
        """Test HTML href and src attributes are extracted."""
        mock_config_cls.load.return_value = mock_config
        mock_explain_path.return_value = (True, [])
        vault_mock = MagicMock(vault_path=Path("/mock/vault"), links_dir=Path("/mock/vault/_links"))
        vault_mock.resolve_link.side_effect = lambda t: MagicMock(target_uri=t)
        mock_vault_cls.return_value.__enter__ = MagicMock(return_value=vault_mock)
        mock_vault_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = cmd_check(str(temp_html_file))
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        links = result.output["links"]

        # Should find href and src
        uris = [lnk["to_local_uri"] for lnk in links]
        assert "https://example.com" in uris
        assert "image.png" in uris

    @patch("wks.api.link.cmd_check.WKSConfig")
    @patch("wks.api.link.cmd_check.explain_path")
    @patch("wks.api.link.cmd_check.Vault")
    def test_rst_links_extracted(self, mock_vault_cls, mock_explain_path, mock_config_cls, mock_config, temp_rst_file):
        """Test RST links and images are extracted."""
        mock_config_cls.load.return_value = mock_config
        mock_explain_path.return_value = (True, [])
        vault_mock = MagicMock(vault_path=Path("/mock/vault"), links_dir=Path("/mock/vault/_links"))
        vault_mock.resolve_link.side_effect = lambda t: MagicMock(target_uri=t)
        mock_vault_cls.return_value.__enter__ = MagicMock(return_value=vault_mock)
        mock_vault_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = cmd_check(str(temp_rst_file))
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        links = result.output["links"]

        uris = [lnk["to_local_uri"] for lnk in links]
        assert "https://example.com" in uris
        assert "diagram.png" in uris

    @patch("wks.api.link.cmd_check.WKSConfig")
    @patch("wks.api.link.cmd_check.explain_path")
    @patch("wks.api.link.cmd_check.Vault")
    def test_raw_urls_extracted(self, mock_vault_cls, mock_explain_path, mock_config_cls, mock_config, temp_txt_file):
        """Test plain URLs are extracted from text files."""
        mock_config_cls.load.return_value = mock_config
        mock_explain_path.return_value = (True, [])
        vault_mock = MagicMock(vault_path=Path("/mock/vault"), links_dir=Path("/mock/vault/_links"))
        vault_mock.resolve_link.side_effect = lambda t: MagicMock(target_uri=t)
        mock_vault_cls.return_value.__enter__ = MagicMock(return_value=vault_mock)
        mock_vault_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = cmd_check(str(temp_txt_file))
        for _ in result.progress_callback(result):
            pass

        assert result.success is True
        links = result.output["links"]

        uris = [lnk["to_local_uri"] for lnk in links]
        assert any("example.com" in uri for uri in uris)
        assert any("another.com" in uri for uri in uris)

    @patch("wks.api.link.cmd_check.WKSConfig")
    @patch("wks.api.link.cmd_check.explain_path")
    @patch("wks.api.link.cmd_check.Vault")
    def test_line_and_column_numbers_captured(
        self, mock_vault_cls, mock_explain_path, mock_config_cls, mock_config, temp_markdown_file
    ):
        """Test that line and column numbers are captured for each link."""
        mock_config_cls.load.return_value = mock_config
        mock_explain_path.return_value = (True, [])
        vault_mock = MagicMock(vault_path=Path("/mock/vault"), links_dir=Path("/mock/vault/_links"))
        vault_mock.resolve_link.side_effect = lambda t: MagicMock(target_uri=t)
        mock_vault_cls.return_value.__enter__ = MagicMock(return_value=vault_mock)
        mock_vault_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = cmd_check(str(temp_markdown_file))
        for _ in result.progress_callback(result):
            pass

        links = result.output["links"]

        for link in links:
            assert "line_number" in link
            assert "column_number" in link
            assert link["line_number"] >= 1
            assert link["column_number"] >= 1

    @patch("wks.api.link.cmd_check.WKSConfig")
    @patch("wks.api.link.cmd_check.explain_path")
    @patch("wks.api.link.cmd_check.Vault")
    def test_parser_field_populated(
        self, mock_vault_cls, mock_explain_path, mock_config_cls, mock_config, temp_markdown_file
    ):
        """Test that parser field is populated for each link."""
        mock_config_cls.load.return_value = mock_config
        mock_explain_path.return_value = (True, [])
        vault_mock = MagicMock(vault_path=Path("/mock/vault"), links_dir=Path("/mock/vault/_links"))
        vault_mock.resolve_link.side_effect = lambda t: MagicMock(target_uri=t)
        mock_vault_cls.return_value.__enter__ = MagicMock(return_value=vault_mock)
        mock_vault_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = cmd_check(str(temp_markdown_file))
        for _ in result.progress_callback(result):
            pass

        links = result.output["links"]

        for link in links:
            assert "parser" in link
            assert link["parser"] in ("auto", "markdown", "vault", "obsidian")
