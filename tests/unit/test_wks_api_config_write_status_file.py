import json

from wks.api.config.write_status_file import write_status_file


def test_write_status_file(tmp_path):
    """Test that write_status_file writes the correct JSON file."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()

    status_data = {
        "running": True,
        "pid": 12345,
    }

    write_status_file(status_data, wks_home=wks_home, filename="test.json")

    target_file = wks_home / "test.json"
    assert target_file.exists()

    content = json.loads(target_file.read_text())
    assert content["running"] is True
    assert content["pid"] == 12345
    assert content == status_data


def test_write_status_file_creates_parent_dir(tmp_path):
    """Test that write_status_file creates the parent directory if it doesn't exist."""
    wks_home = tmp_path / ".wks_new"

    status_data = {"running": False}

    write_status_file(status_data, wks_home=wks_home, filename="subdir/status.json")

    target_file = wks_home / "subdir/status.json"
    assert target_file.exists()
    assert json.loads(target_file.read_text()) == status_data
