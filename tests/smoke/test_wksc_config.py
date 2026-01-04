def test_cli_config_show(wksc):
    """Test 'wksc config show' - outputs JSON with config keys."""
    result = wksc(["config", "show", "monitor"])
    # Output contains JSON with monitor key (or content of monitor section)
    assert "priority" in result.stdout


def test_cli_config_list(wksc):
    """Test 'wksc config list' lists available sections."""
    result = wksc(["config", "list"])
    assert "monitor" in result.stdout
    assert "database" in result.stdout
