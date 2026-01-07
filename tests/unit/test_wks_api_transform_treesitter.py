"""Tests for tree-sitter transform engine."""

from wks.api.config.URI import URI
from wks.api.transform._EngineConfig import _EngineConfig
from wks.api.transform.cmd_engine import cmd_engine


def test_cmd_engine_treesitter_infers_language(tracked_wks_config, tmp_path):
    tracked_wks_config.transform.engines["ast_ts"] = _EngineConfig(
        type="treesitter", data={"language": "auto", "format": "sexp"}
    )

    source = tmp_path / "example.py"
    source.write_text("def hello():\n    return 42\n", encoding="utf-8")

    result = cmd_engine("ast_ts", URI.from_path(source), overrides={})
    list(result.progress_callback(result))

    assert result.success is True
    destination = URI(result.output["destination_uri"]).path
    assert destination.exists()
    assert destination.suffix == ".sexp"
