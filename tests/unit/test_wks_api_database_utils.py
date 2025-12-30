from wks.api.database._get_last_prune_timestamp import _get_last_prune_timestamp


def test_prune_timestamp_io_errors(tmp_path, monkeypatch):
    """Test error handling in timestamp utilities."""
    from wks.api.database import _get_status_path

    monkeypatch.setattr(_get_status_path, "_get_status_path", lambda: tmp_path / "missing" / "status.json")

    # Test _get_last_prune_timestamp error (hits except block)
    # We'll mock json.loads to raise
    import json

    monkeypatch.setattr(json, "loads", lambda x: exec("raise Exception('fail')"))

    # Setup a file so it tries to load it
    status_path = tmp_path / "status.json"
    status_path.write_text("{}")
    monkeypatch.setattr(_get_status_path, "_get_status_path", lambda: status_path)

    assert _get_last_prune_timestamp("db") is None
