import json

import pytest

from tests.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.index.cmd_auto import cmd_auto


def make_auto_env(tmp_path, monkeypatch, *, priority_dirs=None, indexes=None, extra_engines=None):
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
    if extra_engines:
        config_dict["transform"]["engines"].update(extra_engines)

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    config_path = wks_home / "config.json"
    config_path.write_text(json.dumps(config_dict))
    return cache_dir, config_path


@pytest.mark.parametrize(
    ("priority_value", "index_name", "index_config", "expected_indexed", "expected_skipped"),
    [
        (100.0, "main", {"main": {"engine": "textpass", "min_priority": 50.0}}, ["main"], []),
        (0.0, "main", {"main": {"engine": "textpass", "min_priority": 50.0}}, [], ["main"]),
        (
            75.0,
            "low",
            {
                "low": {"engine": "textpass", "min_priority": 10.0},
                "high": {"engine": "textpass", "min_priority": 200.0},
            },
            ["low"],
            ["high"],
        ),
    ],
)
def test_auto_priority_selection(
    tmp_path, monkeypatch, priority_value, index_name, index_config, expected_indexed, expected_skipped
):
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()
    make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(doc_dir): priority_value} if priority_value else {},
        indexes={"default_index": index_name, "indexes": index_config},
    )

    doc = doc_dir / "test.txt"
    doc.write_text("Nuclear fission products are generated during reactor operation.\n" * 5)

    result = run_cmd(cmd_auto, str(doc))
    assert result.success is True
    assert [item["index_name"] for item in result.output["indexed"]] == expected_indexed
    assert result.output["skipped"] == expected_skipped


def test_auto_no_index_config(tmp_path, monkeypatch):
    make_auto_env(tmp_path, monkeypatch)
    doc = tmp_path / "test.txt"
    doc.write_text("Hello world.\n")

    result = run_cmd(cmd_auto, str(doc))
    assert result.success is True
    assert result.output["indexed"] == []
    assert result.output["skipped"] == []


def test_auto_file_not_found(tmp_path, monkeypatch):
    make_auto_env(
        tmp_path,
        monkeypatch,
        indexes={"default_index": "main", "indexes": {"main": {"engine": "textpass"}}},
    )

    result = run_cmd(cmd_auto, str(tmp_path / "missing.txt"))
    assert result.success is False
    assert "not found" in result.output["errors"][0].lower()


def test_auto_reports_priority(tmp_path, monkeypatch):
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()
    make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(doc_dir): 42.0},
        indexes={"default_index": "main", "indexes": {"main": {"engine": "textpass", "min_priority": 0.0}}},
    )

    doc = doc_dir / "test.txt"
    doc.write_text("Some content.\n")
    result = run_cmd(cmd_auto, str(doc))

    assert result.success is True
    assert result.output["priority"] == pytest.approx(42.0, rel=0.1)


def test_auto_with_file_uri(tmp_path, monkeypatch):
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()
    make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(doc_dir): 100.0},
        indexes={"default_index": "main", "indexes": {"main": {"engine": "textpass", "min_priority": 50.0}}},
    )

    doc = doc_dir / "test.txt"
    doc.write_text("Content for URI test.\n" * 5)
    result = run_cmd(cmd_auto, str(URI.from_path(doc)))

    assert result.success is True
    assert len(result.output["indexed"]) == 1


def test_auto_skips_transform_cache(tmp_path, monkeypatch):
    cache_dir, _ = make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(tmp_path): 100.0},
        indexes={"default_index": "main", "indexes": {"main": {"engine": "textpass", "min_priority": 0.0}}},
    )
    cache_file = cache_dir / "abc123.md"
    cache_file.write_text("Cached transform output.\n")

    result = run_cmd(cmd_auto, str(cache_file))
    assert result.success is True
    assert result.output["indexed"] == []
    assert "transform cache" in result.result.lower()


def test_auto_skips_unsupported_supported_types(tmp_path, monkeypatch):
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()
    _, config_path = make_auto_env(
        tmp_path,
        monkeypatch,
        priority_dirs={str(doc_dir): 100.0},
        indexes={
            "default_index": "images_semantic",
            "indexes": {"images_semantic": {"engine": "img_caption", "min_priority": 0.0}},
        },
        extra_engines={
            "img_caption": {
                "type": "imagetext",
                "data": {"model": "test-model", "max_new_tokens": 16},
                "supported_types": [".png", ".jpg", ".jpeg", ".webp"],
            }
        },
    )

    config = json.loads(config_path.read_text())
    config_path.write_text(json.dumps(config))
    doc = doc_dir / "notes.txt"
    doc.write_text("not an image\n")

    result = run_cmd(cmd_auto, str(doc))
    assert result.success is True
    assert result.output["indexed"] == []
    assert "images_semantic" in result.output["skipped"]


def test_auto_honors_supported_types_per_engine(tmp_path, monkeypatch):
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()
    make_auto_env(
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
        extra_engines={
            "txtpass": {"type": "textpass", "data": {}, "supported_types": [".txt"]},
            "mdpass": {"type": "textpass", "data": {}, "supported_types": [".md"]},
        },
    )

    doc = doc_dir / "report.txt"
    doc.write_text("Textpass test content.\n")

    result = run_cmd(cmd_auto, str(doc))
    assert result.success is True
    assert [item["index_name"] for item in result.output["indexed"]] == ["txt_idx"]
    assert "md_idx" in result.output["skipped"]
