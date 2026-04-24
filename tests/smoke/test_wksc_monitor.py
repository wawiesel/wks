def test_cli_monitor_status(wksc):
    result = wksc(["monitor", "status"])
    assert "tracked_files" in result.stdout
