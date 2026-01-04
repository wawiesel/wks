def test_cli_vault_sync(wksc, smoke_env):
    """Test 'wksc vault sync'."""
    # Ensure vault has content
    vault_dir = smoke_env["vault"]
    if not (vault_dir / "smoke_test.md").exists():
        (vault_dir / "smoke_test.md").write_text("# Smoke Test\n[[Link]]", encoding="utf-8")

    result = wksc(["vault", "sync"])

    # Verify sync success output
    assert "notes_scanned" in result.stdout
    assert "links_written" in result.stdout
    assert "success" in result.stdout
