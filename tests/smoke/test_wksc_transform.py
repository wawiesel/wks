def test_cli_transform_raw(wksc, smoke_env):
    """Test 'wksc transform --raw' outputs checksum only."""
    home_dir = smoke_env["home"]
    test_file = home_dir / "test_raw.txt"
    test_file.write_text("Hello Raw", encoding="utf-8")

    result = wksc(["transform", "--raw", "-e", "textpass", str(test_file)])

    output = result.stdout.strip()
    import re

    assert re.match(r"^[a-f0-9]{64}$", output)


def test_cli_transform_uses_default_engine(wksc, smoke_env):
    """Test 'wksc transform <file>' uses transform.default_engine."""
    home_dir = smoke_env["home"]
    test_file = home_dir / "test_default.txt"
    test_file.write_text("Hello Default", encoding="utf-8")

    result = wksc(["transform", "--raw", str(test_file)])
    output = result.stdout.strip()

    import re

    assert re.match(r"^[a-f0-9]{64}$", output)


def test_cli_transform_rejects_legacy_positional_engine_form(wksc, smoke_env):
    """Test the retired positional engine form fails with a clear message."""
    home_dir = smoke_env["home"]
    test_file = home_dir / "test_positional.txt"
    test_file.write_text("Hello Legacy", encoding="utf-8")

    result = wksc(["transform", "textpass", str(test_file)], check=False)

    assert result.returncode != 0
    error_text = f"{result.stdout}\n{result.stderr}".lower()
    assert "unexpected positional argument" in error_text
    assert "--engine/-e" in error_text or "--engine" in error_text
