"""Tests for tree-sitter transform engine."""

import pytest

from wks.api.config.URI import URI
from wks.api.transform.cmd_engine import cmd_engine
from wks.api.transform._EngineConfig import _EngineConfig


@pytest.mark.transform
def test_cmd_engine_treesitter_infers_language(tracked_wks_config, tmp_path):
    pytest.importorskip("tree_sitter_languages")

    tracked_wks_config.transform.engines["ast_ts"] = _EngineConfig(type="treesitter", data={})

    source = tmp_path / "example.py"
    source.write_text("def hello():\n    return 42\n", encoding="utf-8")

    result = cmd_engine("ast_ts", URI.from_path(source), overrides={})
    list(result.progress_callback(result))

    assert result.success is True
    destination = URI(result.output["destination_uri"]).path
    assert destination.exists()
    assert destination.suffix == ".ast"
