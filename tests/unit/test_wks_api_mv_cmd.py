"""Unit tests for the mv command wrapper."""

from tests.unit.conftest import run_cmd
from wks.api.mv.cmd import cmd


def test_mv_cmd_returns_wrapped_move_output(monkeypatch, tracked_wks_config, tmp_path):
    """The mv command should preserve the command contract over the shared move service."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()
    tracked_wks_config.monitor.filter.include_paths.extend([str(source_dir), str(dest_dir)])

    source_file = source_dir / "notes.txt"
    dest_file = dest_dir / "notes.txt"
    source_file.write_text("move me", encoding="utf-8")

    monkeypatch.setattr("wks.services.mv._update_move_side_effects", lambda *_args: (True, []))

    result = run_cmd(cmd, str(source_file), str(dest_file))

    assert result.success is True
    assert result.output["source"] == str(source_file)
    assert result.output["destination"] == str(dest_file)
    assert result.output["database_updated"] is True
