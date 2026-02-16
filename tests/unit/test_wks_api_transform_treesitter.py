"""Tests for tree-sitter transform engine."""

from tests.unit.conftest import create_tracked_wks_config, run_cmd
from wks.api.config.URI import URI
from wks.api.transform.cmd_engine import cmd_engine


def test_cmd_engine_treesitter_infers_language(tmp_path, monkeypatch, minimal_config_dict):
    minimal_config_dict["transform"]["engines"]["ast_ts"] = {
        "type": "treesitter",
        "data": {"language": "auto", "format": "sexp"},
    }
    create_tracked_wks_config(monkeypatch, config_dict=minimal_config_dict)

    source = tmp_path / "example.py"
    source.write_text("def hello():\n    return 42\n", encoding="utf-8")

    result = run_cmd(cmd_engine, engine="ast_ts", uri=URI.from_path(source), overrides={})
    assert result.success is True
    destination = URI(result.output["destination_uri"]).path
    assert destination.exists()
    assert destination.suffix == ".sexp"


def test_treesitter_language_none(tmp_path, monkeypatch, minimal_config_dict):
    """Treesitter engine rejects language=None."""
    minimal_config_dict["transform"]["engines"]["ts"] = {
        "type": "treesitter",
        "data": {"language": None, "format": "sexp"},
    }
    create_tracked_wks_config(monkeypatch, config_dict=minimal_config_dict)

    source = tmp_path / "test.py"
    source.write_text("x = 1")

    result = run_cmd(cmd_engine, engine="ts", uri=URI.from_path(source), overrides={})
    assert result.success is False
    assert "language" in result.result.lower()


def test_treesitter_language_empty(tmp_path, monkeypatch, minimal_config_dict):
    """Treesitter engine rejects empty language string."""
    minimal_config_dict["transform"]["engines"]["ts"] = {
        "type": "treesitter",
        "data": {"language": "", "format": "sexp"},
    }
    create_tracked_wks_config(monkeypatch, config_dict=minimal_config_dict)

    source = tmp_path / "test.py"
    source.write_text("x = 1")

    result = run_cmd(cmd_engine, engine="ts", uri=URI.from_path(source), overrides={})
    assert result.success is False
    assert "language" in result.result.lower()


def test_treesitter_format_non_sexp(tmp_path, monkeypatch, minimal_config_dict):
    """Treesitter engine rejects non-sexp format."""
    minimal_config_dict["transform"]["engines"]["ts"] = {
        "type": "treesitter",
        "data": {"language": "python", "format": "json"},
    }
    create_tracked_wks_config(monkeypatch, config_dict=minimal_config_dict)

    source = tmp_path / "test.py"
    source.write_text("x = 1")

    result = run_cmd(cmd_engine, engine="ts", uri=URI.from_path(source), overrides={})
    assert result.success is False
    assert "sexp" in result.result.lower()


def test_treesitter_output_contains_ast_nodes(tmp_path, monkeypatch, minimal_config_dict):
    """Verify sexp output contains expected AST node types for Python."""
    minimal_config_dict["transform"]["engines"]["ast_ts"] = {
        "type": "treesitter",
        "data": {"language": "auto", "format": "sexp"},
    }
    create_tracked_wks_config(monkeypatch, config_dict=minimal_config_dict)

    source = tmp_path / "example.py"
    source.write_text("x = 1\n", encoding="utf-8")

    result = run_cmd(cmd_engine, engine="ast_ts", uri=URI.from_path(source), overrides={})
    assert result.success is True

    destination = URI(result.output["destination_uri"]).path
    content = destination.read_text(encoding="utf-8")

    # sexp output must contain recognizable AST nodes
    assert "module" in content
    assert "expression_statement" in content or "assignment" in content


def test_treesitter_output_ends_with_newline(tmp_path, monkeypatch, minimal_config_dict):
    """Output file must end with a trailing newline."""
    minimal_config_dict["transform"]["engines"]["ast_ts"] = {
        "type": "treesitter",
        "data": {"language": "auto", "format": "sexp"},
    }
    create_tracked_wks_config(monkeypatch, config_dict=minimal_config_dict)

    source = tmp_path / "hello.py"
    source.write_text("pass\n", encoding="utf-8")

    result = run_cmd(cmd_engine, engine="ast_ts", uri=URI.from_path(source), overrides={})
    assert result.success is True

    destination = URI(result.output["destination_uri"]).path
    content = destination.read_text(encoding="utf-8")
    assert content.endswith("\n")
