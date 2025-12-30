from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.link.cmd_sync import cmd_sync


def test_parsers_coverage(tracked_wks_config, tmp_path):
    """Test various parsers (HTML, RST, Raw) to reach 100% in link domain."""
    monitored_root = tmp_path / "monitored"
    monitored_root.mkdir()
    tracked_wks_config.monitor.filter.include_paths = [str(monitored_root)]

    # 1. HTML Parser (edge cases: empty href, fragments + valid link/image)
    html_file = monitored_root / "test.html"
    html_content = (
        '<a href="">none</a> <a href="#top">top</a> <img src=""> <a href="http://e.com">ok</a> <img src="i.png">'
    )
    html_file.write_text(html_content, encoding="utf-8")

    # 2. RST Parser
    rst_file = monitored_root / "test.rst"
    rst_file.write_text("`link <http://example.com>`_\n\n.. image:: img.png", encoding="utf-8")

    # 3. Raw Parser
    raw_file = monitored_root / "test.txt"
    raw_file.write_text("Check http://example.com and https://google.com", encoding="utf-8")

    # 4. Markdown Parser
    md_file = monitored_root / "test.md"
    md_content = "[link](http://m.com) ![img](http://i.com) [[target|alias]] [[target2\\|alias2]]"
    md_file.write_text(md_content, encoding="utf-8")

    # Sync all
    result = run_cmd(cmd_sync, path=str(monitored_root), recursive=True)
    assert result.success is True
    assert result.output["links_found"] >= 7


def test_get_parser_invalid(tracked_wks_config):
    """Test invalid parser name or unknown extension (lines 38, 49)."""
    from wks.api.link._parsers import RawParser, get_parser

    # 1. Unknown extension
    assert get_parser(file_path=Path("test.unknown")).__class__ == RawParser

    # 2. Invalid name
    with pytest.raises(ValueError, match="Unknown parser: invalid"):
        get_parser("invalid", Path("test.md"))
