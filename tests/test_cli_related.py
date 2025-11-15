"""Tests for wks0 related command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_related_basic_table_output(tmp_path, monkeypatch):
    """Test wks0 related with table output format."""
    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is a test document for similarity search.")

    # Mock the similarity database
    mock_db = MagicMock()
    mock_db.find_similar.return_value = [
        ("file:///path/to/similar1.txt", 0.92),
        ("file:///path/to/similar2.pdf", 0.78),
        ("/path/to/similar3.docx", 0.65),
    ]
    mock_db.client.close = MagicMock()

    def mock_load_similarity():
        return mock_db, {}

    monkeypatch.setattr("wks.cli._load_similarity_required", mock_load_similarity)

    # Run command
    from wks.cli import main
    result = main(["related", str(test_file)])

    assert result == 0
    mock_db.find_similar.assert_called_once()
    call_kwargs = mock_db.find_similar.call_args[1]
    assert call_kwargs['limit'] == 10
    assert call_kwargs['min_similarity'] == 0.0
    assert call_kwargs['mode'] == "file"


def test_related_json_output(tmp_path, monkeypatch, capsys):
    """Test wks0 related with JSON output format."""
    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is a test document.")

    # Mock the similarity database
    mock_db = MagicMock()
    mock_db.find_similar.return_value = [
        ("file:///path/to/doc1.txt", 0.95),
        ("/path/to/doc2.pdf", 0.82),
    ]
    mock_db.client.close = MagicMock()

    def mock_load_similarity():
        return mock_db, {}

    monkeypatch.setattr("wks.cli._load_similarity_required", mock_load_similarity)

    # Run command
    from wks.cli import main
    result = main(["related", str(test_file), "--format", "json"])

    assert result == 0

    # Check JSON output
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert len(output) == 2
    assert output[0]["path"] == "/path/to/doc1.txt"
    assert output[0]["similarity"] == 0.95
    assert output[1]["path"] == "/path/to/doc2.pdf"
    assert output[1]["similarity"] == 0.82


def test_related_with_limit(tmp_path, monkeypatch):
    """Test wks0 related with custom limit."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")

    mock_db = MagicMock()
    mock_db.find_similar.return_value = []
    mock_db.client.close = MagicMock()

    def mock_load_similarity():
        return mock_db, {}

    monkeypatch.setattr("wks.cli._load_similarity_required", mock_load_similarity)

    from wks.cli import main
    result = main(["related", str(test_file), "--limit", "5"])

    assert result == 0
    call_kwargs = mock_db.find_similar.call_args[1]
    assert call_kwargs['limit'] == 5


def test_related_with_min_similarity(tmp_path, monkeypatch):
    """Test wks0 related with minimum similarity threshold."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")

    mock_db = MagicMock()
    mock_db.find_similar.return_value = []
    mock_db.client.close = MagicMock()

    def mock_load_similarity():
        return mock_db, {}

    monkeypatch.setattr("wks.cli._load_similarity_required", mock_load_similarity)

    from wks.cli import main
    result = main(["related", str(test_file), "--min-similarity", "0.7"])

    assert result == 0
    call_kwargs = mock_db.find_similar.call_args[1]
    assert call_kwargs['min_similarity'] == 0.7


def test_related_file_not_found(tmp_path):
    """Test wks0 related with non-existent file."""
    from wks.cli import main
    nonexistent = tmp_path / "nonexistent.txt"

    result = main(["related", str(nonexistent)])
    assert result == 2


def test_related_no_results(tmp_path, monkeypatch, capsys):
    """Test wks0 related when no similar documents are found."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")

    mock_db = MagicMock()
    mock_db.find_similar.return_value = []
    mock_db.client.close = MagicMock()

    def mock_load_similarity():
        return mock_db, {}

    monkeypatch.setattr("wks.cli._load_similarity_required", mock_load_similarity)

    from wks.cli import main
    result = main(["related", str(test_file)])

    assert result == 0
    captured = capsys.readouterr()
    assert "No similar documents found" in captured.out


def test_related_database_error(tmp_path, monkeypatch):
    """Test wks0 related handles database errors gracefully."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")

    def mock_load_similarity():
        raise Exception("Database connection failed")

    monkeypatch.setattr("wks.cli._load_similarity_required", mock_load_similarity)

    from wks.cli import main
    result = main(["related", str(test_file)])

    assert result == 2


def test_related_find_similar_error(tmp_path, monkeypatch):
    """Test wks0 related handles find_similar errors gracefully."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")

    mock_db = MagicMock()
    mock_db.find_similar.side_effect = Exception("Query failed")
    mock_db.client.close = MagicMock()

    def mock_load_similarity():
        return mock_db, {}

    monkeypatch.setattr("wks.cli._load_similarity_required", mock_load_similarity)

    from wks.cli import main
    result = main(["related", str(test_file)])

    assert result == 2
