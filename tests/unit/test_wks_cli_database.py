"""Unit tests for wks.cli.database."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from wks.cli.database import db_app

runner = CliRunner()


@patch("wks.api.database.cmd_prune.cmd_prune")
@patch("wks.cli.database.handle_stage_result")
def test_prune_all(mock_handle_stage_result, mock_cmd_prune):
    """Test prune all command calls api with 'all'."""
    # Setup handle_stage_result to return a mock that can be called
    mock_executor = MagicMock()
    mock_handle_stage_result.return_value = mock_executor

    result = runner.invoke(db_app, ["prune", "all"])

    assert result.exit_code == 0

    mock_handle_stage_result.assert_called_with(mock_cmd_prune)
    mock_executor.assert_called_with(database="all", remote=False)


@patch("wks.api.database.cmd_prune.cmd_prune")
@patch("wks.cli.database.handle_stage_result")
def test_prune_nodes(mock_handle_stage_result, mock_cmd_prune):
    """Test prune nodes calls api with 'nodes'."""
    mock_executor = MagicMock()
    mock_handle_stage_result.return_value = mock_executor

    result = runner.invoke(db_app, ["prune", "nodes"])

    assert result.exit_code == 0
    mock_handle_stage_result.assert_called_with(mock_cmd_prune)
    mock_executor.assert_called_with(database="nodes", remote=False)


@patch("wks.api.database.cmd_prune.cmd_prune")
@patch("wks.cli.database.handle_stage_result")
def test_prune_edges_remote(mock_handle_stage_result, mock_cmd_prune):
    """Test prune edges with remote flag calls api with 'edges' and remote=True."""
    mock_executor = MagicMock()
    mock_handle_stage_result.return_value = mock_executor

    result = runner.invoke(db_app, ["prune", "edges", "--remote"])

    assert result.exit_code == 0
    mock_handle_stage_result.assert_called_with(mock_cmd_prune)
    mock_executor.assert_called_with(database="edges", remote=True)


def test_prune_no_args_shows_help():
    """Test that prune without args shows help."""
    result = runner.invoke(db_app, ["prune"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout


def test_prune_invalid_db():
    """Test prune with invalid database name."""
    result = runner.invoke(db_app, ["prune", "invalid_db"])
    assert result.exit_code == 1
    assert "Error: Unknown database 'invalid_db'" in result.stderr
