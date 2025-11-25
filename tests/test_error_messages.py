"""Tests for error message formatting."""

import pytest
from unittest.mock import patch
import pymongo.errors


def test_mongodb_connection_error(capsys):
    """Test MongoDB connection error message formatting."""
    from wks.error_messages import mongodb_connection_error

    with pytest.raises(SystemExit) as exc_info:
        mongodb_connection_error(
            "mongodb://localhost:27017/",
            pymongo.errors.ServerSelectionTimeoutError("Connection timeout")
        )

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "MONGODB CONNECTION FAILED" in captured.err
    assert "mongodb://localhost:27017/" in captured.err
    assert "Connection timeout" in captured.err
    assert "brew services start mongodb-community" in captured.err


def test_missing_dependency_error(capsys):
    """Test missing dependency error message formatting."""
    from wks.error_messages import missing_dependency_error

    import_error = ImportError("No module named 'sentence_transformers'")

    with pytest.raises(SystemExit) as exc_info:
        missing_dependency_error("sentence-transformers", import_error)

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "MISSING DEPENDENCY: sentence-transformers" in captured.err
    assert "pip install -e '.[all]'" in captured.err


def test_file_permission_error(capsys):
    """Test file permission error message formatting."""
    from wks.error_messages import file_permission_error

    perm_error = PermissionError("[Errno 13] Permission denied")

    with pytest.raises(SystemExit) as exc_info:
        file_permission_error("/path/to/file.txt", "read", perm_error)

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "FILE PERMISSION ERROR" in captured.err
    assert "/path/to/file.txt" in captured.err
    assert "read" in captured.err
    assert "chmod u+rw" in captured.err


def test_vault_path_error(capsys):
    """Test vault path error message formatting."""
    from wks.error_messages import vault_path_error

    with pytest.raises(SystemExit) as exc_info:
        vault_path_error("/nonexistent/vault")

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "INVALID OBSIDIAN VAULT PATH" in captured.err
    assert "/nonexistent/vault" in captured.err
    assert "vault_path" in captured.err


def test_model_download_error(capsys):
    """Test model download error message formatting."""
    from wks.error_messages import model_download_error

    http_error = Exception("Connection refused")

    with pytest.raises(SystemExit) as exc_info:
        model_download_error("all-MiniLM-L6-v2", http_error)

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "MODEL DOWNLOAD FAILED" in captured.err
    assert "all-MiniLM-L6-v2" in captured.err
    assert "Connection refused" in captured.err
    assert "huggingface.co" in captured.err
