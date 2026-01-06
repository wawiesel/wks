def test_cli_transform_raw(wksc, smoke_env):
    """Test 'wksc transform --raw' outputs checksum only."""
    # Ensure test file exists
    home_dir = smoke_env["home"]
    test_file = home_dir / "test_raw.txt"
    test_file.write_text("Hello Raw", encoding="utf-8")

    result = wksc(["transform", "--raw", "textpass", str(test_file)])

    # Check output is exactly the checksum (hex string) usually 64 chars
    output = result.stdout.strip()
    # Hex string
    import re

    assert re.match(r"^[a-f0-9]{64}$", output)
