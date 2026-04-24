import numpy as np
import pytest

from tests.unit.conftest import run_cmd
from wks.api.diff.cmd_diff import cmd_diff

pytestmark = pytest.mark.unit


def build_config(engine: str | None = "myers", **engine_overrides):
    engine_config = None if engine is None else {"engine": engine, **engine_overrides}
    config: dict[str, object] = {"timeout_seconds": 60, "max_size_mb": 100}
    if engine_config is not None:
        config["engine_config"] = engine_config
    return config


def write_pair(tmp_path, content_a, content_b, *, suffix=".txt", binary=False):
    file_a = tmp_path / f"a{suffix}"
    file_b = tmp_path / f"b{suffix}"
    if binary:
        file_a.write_bytes(content_a)
        file_b.write_bytes(content_b)
    else:
        file_a.write_text(content_a)
        file_b.write_text(content_b)
    return file_a, file_b


@pytest.mark.parametrize(
    ("engine", "suffix", "content_a", "content_b", "binary", "metadata_key", "metadata_value"),
    [
        ("myers", ".txt", "hello\nworld\n", "hello\nuniverse\n", False, "engine_used", "myers"),
        ("myers", ".txt", "identical content\n", "identical content\n", False, "is_identical", True),
        (
            "sexp",
            ".sexp",
            "(module (function (name hello)))",
            "(module (function (name world)))",
            False,
            "engine_used",
            "sexp",
        ),
        ("bsdiff3", ".bin", b"binary data 1", b"binary data 2", True, "engine_used", "bsdiff3"),
    ],
)
def test_cmd_diff_success_cases(tmp_path, engine, suffix, content_a, content_b, binary, metadata_key, metadata_value):
    file_a, file_b = write_pair(tmp_path, content_a, content_b, suffix=suffix, binary=binary)
    result = run_cmd(cmd_diff, build_config(engine), str(file_a), str(file_b))

    assert result.success
    assert result.output["status"] == "success"
    assert result.output["metadata"][metadata_key] == metadata_value


def test_cmd_diff_myers_with_options(tmp_path):
    file_a, file_b = write_pair(tmp_path, "hello\nworld\n", "hello\nuniverse\n")
    result = run_cmd(
        cmd_diff,
        build_config("myers", context_lines=5, ignore_whitespace=True),
        str(file_a),
        str(file_b),
    )
    assert result.success
    assert result.output["status"] == "success"


def test_cmd_diff_success_semantic_text(tmp_path, monkeypatch):
    file_a, file_b = write_pair(tmp_path, "hello world\nfission data\n", "hello universe\nfission dataset\n")

    def fake_embed(texts, model_name, batch_size):
        del model_name, batch_size
        if "world" in texts[0]:
            return np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        return np.array([[0.95, 0.1], [0.05, 0.99]], dtype=np.float32)

    monkeypatch.setattr("wks.api.index._embedding_utils.embed_texts", fake_embed)
    result = run_cmd(
        cmd_diff,
        build_config(
            "semantic",
            modified_threshold=0.6,
            unchanged_threshold=0.95,
            text_model="test-text-model",
            image_model="test-image-model",
            pixel_threshold=5,
            max_examples=8,
        ),
        str(file_a),
        str(file_b),
    )

    assert result.success
    assert result.output["status"] == "success"
    assert result.output["metadata"]["engine_used"] == "semantic"
    assert result.output["diff_output"] is not None


@pytest.mark.parametrize(
    ("config", "target_a", "target_b", "expected_error"),
    [
        (None, "a.txt", "b.txt", "config must be a dict"),
        ({"timeout_seconds": 60, "max_size_mb": 100}, "a.txt", "b.txt", "config.engine_config is required"),
        (build_config("invalid_engine"), "a.txt", "b.txt", "must be one of auto,bsdiff3,myers,sexp,semantic"),
        (build_config("myers"), "", "some_file", "target_a is required"),
        (build_config("myers"), "some_file", "", "target_b is required"),
        (build_config("myers", **{}), "a.txt", "b.txt", "not found"),
        (
            {"engine_config": {"engine": "myers"}, "timeout_seconds": -1, "max_size_mb": 100},
            "a.txt",
            "b.txt",
            "timeout_seconds must be a positive int",
        ),
        (
            {"engine_config": {"engine": "myers"}, "timeout_seconds": 60, "max_size_mb": 0},
            "a.txt",
            "b.txt",
            "max_size_mb must be a positive int",
        ),
    ],
)
def test_cmd_diff_validation_errors(tmp_path, config, target_a, target_b, expected_error):
    if target_a and expected_error != "not found":
        (tmp_path / target_a).write_text("A")
    if target_b and expected_error != "not found":
        (tmp_path / target_b).write_text("B")
    actual_a = str(tmp_path / target_a) if target_a and target_a.endswith(".txt") else target_a
    actual_b = str(tmp_path / target_b) if target_b and target_b.endswith(".txt") else target_b

    result = run_cmd(cmd_diff, config, actual_a, actual_b)
    assert not result.success
    assert (
        expected_error in result.output["error_details"]["errors"][0].lower()
        if expected_error == "not found"
        else expected_error in result.output["error_details"]["errors"][0]
    )


def test_cmd_diff_failure_file_too_large(tmp_path):
    file_a, file_b = write_pair(tmp_path, "x" * (2 * 1024 * 1024), "x" * (2 * 1024 * 1024))
    result = run_cmd(
        cmd_diff,
        {"engine_config": {"engine": "myers"}, "timeout_seconds": 60, "max_size_mb": 1},
        str(file_a),
        str(file_b),
    )

    assert not result.success
    assert "exceeds max_size_mb" in result.output["error_details"]["errors"][0]


def test_cmd_diff_semantic_requires_all_options(tmp_path):
    file_a, file_b = write_pair(tmp_path, "hello world\n", "hello universe\n")
    result = run_cmd(
        cmd_diff,
        build_config("semantic", modified_threshold=0.6),
        str(file_a),
        str(file_b),
    )

    assert result.success is False
    assert "missing required semantic options" in result.output["error_details"]["errors"][0]
