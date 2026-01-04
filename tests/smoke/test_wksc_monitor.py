def test_cli_monitor_status(wksc):
    """Test 'wksc monitor status' - outputs JSON with tracked_files."""
    result = wksc(["monitor", "status"])
    assert "tracked_files" in result.stdout
