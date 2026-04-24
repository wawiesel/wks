def test_cli_config_show(wksc):
    result = wksc(["config", "show", "monitor"])
    assert "priority" in result.stdout


def test_cli_config_list(wksc):
    result = wksc(["config", "list"])
    assert "monitor" in result.stdout
    assert "database" in result.stdout
