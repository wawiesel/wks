"""Auto-index command tests.

Tests the public cmd_auto(uri) function which auto-indexes a file
into all indexes whose min_priority threshold is met.
"""

import json

import pytest

from tests.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.index.cmd_auto import cmd_auto


def _make_auto_env(tmp_path, monkeypatch, *, priority_dirs=None, indexes=None):
    """Set up an environment with monitor priority dirs and index config."""
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))

    if priority_dirs is not None:
        config_dict["monitor"]["priority"]["dirs"] = priority_dirs

    if indexes is not None:
        config_dict["index"] = indexes

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    return {"cache_dir": cache_dir}


def test_auto_no_index_config(tmp_path, monkeypatch):
    """No index config → success with 0 indexed."""
    _make_auto_env(tmp_path, monkeypatch)

    doc = tmp_path / "test.txt"
    doc.write_text("Hello world.\n")

    result = run_cmd(cmd_auto, str(doc))
    assert result.success is True
    assert result.output["indexed"] == []
    assert result.output["skipped"] == []


def test_auto_indexes_matching(tmp_path, monkeypatch):
    """File with priority above threshold gets indexed."""
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()

    _make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(doc_dir): 100.0},
        indexes={
            "default_index": "main",
            "indexes": {
                "main": {"engine": "textpass", "min_priority": 50.0},
            },
        },
    )

    doc = doc_dir / "test.txt"
    doc.write_text("Nuclear fission products are generated during reactor operation.\n" * 5)

    result = run_cmd(cmd_auto, str(doc))
    assert result.success is True
    assert len(result.output["indexed"]) == 1
    assert result.output["indexed"][0]["index_name"] == "main"
    assert result.output["indexed"][0]["chunk_count"] >= 1
    assert result.output["skipped"] == []
    assert result.output["priority"] >= 50.0


def test_auto_skips_low_priority(tmp_path, monkeypatch):
    """File with priority below threshold is skipped."""
    _make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={},  # No priority dirs → priority = 0
        indexes={
            "default_index": "main",
            "indexes": {
                "main": {"engine": "textpass", "min_priority": 50.0},
            },
        },
    )

    doc = tmp_path / "test.txt"
    doc.write_text("Low priority content.\n")

    result = run_cmd(cmd_auto, str(doc))
    assert result.success is True
    assert result.output["indexed"] == []
    assert "main" in result.output["skipped"]
    assert result.output["priority"] < 50.0


def test_auto_multiple_indexes(tmp_path, monkeypatch):
    """File matches some indexes but not others."""
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()

    _make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(doc_dir): 75.0},
        indexes={
            "default_index": "low",
            "indexes": {
                "low": {"engine": "textpass", "min_priority": 10.0},
                "high": {"engine": "textpass", "min_priority": 200.0},
            },
        },
    )

    doc = doc_dir / "test.txt"
    doc.write_text("Content for indexing.\n" * 5)

    result = run_cmd(cmd_auto, str(doc))
    assert result.success is True
    assert len(result.output["indexed"]) == 1
    assert result.output["indexed"][0]["index_name"] == "low"
    assert "high" in result.output["skipped"]


def test_auto_file_not_found(tmp_path, monkeypatch):
    """Missing file returns error."""
    _make_auto_env(
        tmp_path,
        monkeypatch,
        indexes={
            "default_index": "main",
            "indexes": {"main": {"engine": "textpass"}},
        },
    )

    result = run_cmd(cmd_auto, str(tmp_path / "missing.txt"))
    assert result.success is False
    assert "not found" in result.output["errors"][0].lower()


def test_auto_reports_priority(tmp_path, monkeypatch):
    """Output includes calculated priority."""
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()

    _make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(doc_dir): 42.0},
        indexes={
            "default_index": "main",
            "indexes": {"main": {"engine": "textpass", "min_priority": 0.0}},
        },
    )

    doc = doc_dir / "test.txt"
    doc.write_text("Some content.\n")

    result = run_cmd(cmd_auto, str(doc))
    assert result.success is True
    assert result.output["priority"] == pytest.approx(42.0, rel=0.1)


def test_auto_with_file_uri(tmp_path, monkeypatch):
    """MCP passes file:// URI strings — cmd_auto must resolve to filesystem path."""
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()

    _make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(doc_dir): 100.0},
        indexes={
            "default_index": "main",
            "indexes": {"main": {"engine": "textpass", "min_priority": 50.0}},
        },
    )

    doc = doc_dir / "test.txt"
    doc.write_text("Content for URI test.\n" * 5)

    file_uri = str(URI.from_path(doc))
    result = run_cmd(cmd_auto, file_uri)
    assert result.success is True
    assert len(result.output["indexed"]) == 1


def test_auto_skips_transform_cache(tmp_path, monkeypatch):
    """Files inside the transform cache directory are never auto-indexed."""
    _make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(tmp_path): 100.0},
        indexes={
            "default_index": "main",
            "indexes": {"main": {"engine": "textpass", "min_priority": 0.0}},
        },
    )

    # Create a file inside the transform cache directory
    cache_dir = tmp_path / "transform_cache"
    cache_file = cache_dir / "abc123.md"
    cache_file.write_text("Cached transform output.\n")

    result = run_cmd(cmd_auto, str(cache_file))
    assert result.success is True
    assert result.output["indexed"] == []
    assert "transform cache" in result.result.lower()


def test_auto_skips_unsupported_supported_types(tmp_path, monkeypatch):
    """Index is skipped when file extension is not in engine supported_types."""
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()

    _make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(doc_dir): 100.0},
        indexes={
            "default_index": "images_semantic",
            "indexes": {"images_semantic": {"engine": "img_caption", "min_priority": 0.0}},
        },
    )

    wks_home = tmp_path / "wks_home"
    config_path = wks_home / "config.json"
    config = json.loads(config_path.read_text())
    config["transform"]["engines"]["img_caption"] = {
        "type": "imagetext",
        "data": {"model": "test-model", "max_new_tokens": 16},
        "supported_types": [".png", ".jpg", ".jpeg", ".webp"],
    }
    config_path.write_text(json.dumps(config))

    doc = doc_dir / "notes.txt"
    doc.write_text("not an image\n")

    result = run_cmd(cmd_auto, str(doc))
    assert result.success is True
    assert result.output["indexed"] == []
    assert "images_semantic" in result.output["skipped"]


def test_auto_honors_supported_types_per_engine(tmp_path, monkeypatch):
    """Only indexes with matching supported_types process the file."""
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()

    _make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(doc_dir): 100.0},
        indexes={
            "default_index": "txt_idx",
            "indexes": {
                "txt_idx": {"engine": "txtpass", "min_priority": 0.0},
                "md_idx": {"engine": "mdpass", "min_priority": 0.0},
            },
        },
    )

    wks_home = tmp_path / "wks_home"
    config_path = wks_home / "config.json"
    config = json.loads(config_path.read_text())
    config["transform"]["engines"]["txtpass"] = {
        "type": "textpass",
        "data": {},
        "supported_types": [".txt"],
    }
    config["transform"]["engines"]["mdpass"] = {
        "type": "textpass",
        "data": {},
        "supported_types": [".md"],
    }
    config_path.write_text(json.dumps(config))

    doc = doc_dir / "report.txt"
    doc.write_text("Textpass test content.\n")

    result = run_cmd(cmd_auto, str(doc))
    assert result.success is True
    assert len(result.output["indexed"]) == 1
    assert result.output["indexed"][0]["index_name"] == "txt_idx"
    assert "md_idx" in result.output["skipped"]
