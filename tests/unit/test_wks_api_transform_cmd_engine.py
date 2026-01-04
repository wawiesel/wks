"""Integration tests for transform command using public APIs."""

from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.transform import TransformEngineOutput
from wks.api.transform.cmd_engine import cmd_engine
from wks.api.transform.get_content import get_content
from wks.api.URI import URI


def test_cmd_engine_path_not_found(tracked_wks_config):
    """Test error when path does not exist."""
    result = run_cmd(
        cmd_engine,
        engine="test",
        uri=URI.from_path(Path("/non/existent")),
        overrides={},
    )
    assert result.success is False
    assert "not found" in result.result or "not found" in str(result.output)


def test_cmd_engine_no_engines(tracked_wks_config, tmp_path):
    """Test error when no engines configured."""
    test_f = tmp_path / "test.txt"
    test_f.touch()

    config = WKSConfig.load()
    config.transform.engines = {}
    config.save()

    result = run_cmd(
        cmd_engine,
        engine="test",
        uri=URI.from_path(test_f),
        overrides={},
    )
    assert result.success is False
    assert "No engines" in result.result or "not found" in result.result


def test_cmd_engine_success_and_caching(tracked_wks_config, tmp_path):
    """Test successful transform and caching behavior."""
    test_f = tmp_path / "test.txt"
    test_f.write_text("hello", encoding="utf-8")

    # 1. First run: Should perform transform (cached=False)
    res1 = run_cmd(
        cmd_engine,
        engine="test",
        uri=URI.from_path(test_f),
        overrides={},
    )
    assert res1.success is True
    assert "Transformed" in res1.result
    assert res1.output["cached"] is False
    assert res1.output["checksum"] is not None

    # 2. Second run: Should use cache (cached=True)
    res2 = run_cmd(
        cmd_engine,
        engine="test",
        uri=URI.from_path(test_f),
        overrides={},
    )
    assert res2.success is True
    assert res2.output["cached"] is True
    assert res2.output["checksum"] == res1.output["checksum"]


def test_cmd_engine_fatal_error(tracked_wks_config, tmp_path):
    """Test fatal error during transform (simulated by engine)."""
    test_f = tmp_path / "test.txt"
    test_f.touch()

    # Use the real engine's failure simulation capability
    result = run_cmd(
        cmd_engine,
        engine="test",
        uri=URI.from_path(test_f),
        overrides={"fail_transform": True},
    )
    assert result.success is False
    assert "Simulated transform failure" in result.result


def test_cache_eviction_integration(tracked_wks_config, tmp_path):
    """Test cache eviction by setting small limit and checking behavior."""
    # 1. Update config to small cache
    config = WKSConfig.load()
    # 200 bytes max.
    # Note: TestEngine output is "Transformed: {content}"
    # File overhead + content.
    config.transform.cache.max_size_bytes = 200
    config.save()

    # 2. Transform file 1 (150 bytes content -> ~163 bytes output)
    f1 = tmp_path / "f1.txt"
    f1.write_text("a" * 150)

    res1 = run_cmd(cmd_engine, engine="test", uri=URI.from_path(f1), overrides={})
    assert res1.success is True
    assert res1.output["cached"] is False

    # 3. Transform file 2 (150 bytes content -> ~163 bytes output)
    f2 = tmp_path / "f2.txt"
    f2.write_text("b" * 150)

    res2 = run_cmd(cmd_engine, engine="test", uri=URI.from_path(f2), overrides={})
    assert res2.success is True

    # Total size > 200. f1 should be evicted (LRU).

    # 4. Re-run f1. If evicted, it must re-transform (cached=False).
    res1_again = run_cmd(cmd_engine, engine="test", uri=URI.from_path(f1), overrides={})
    assert res1_again.success is True
    assert res1_again.output["cached"] is False

    # 5. Verify f2 is still cached (was accessed recently)
    # Wait: res2 might have been evicted by res1_again?
    # f1 re-run (163) -> needs space. Current size ~163 (f2 only).
    # 163 + 163 > 200. So f2 must be evicted to fit f1.
    res2_again = run_cmd(cmd_engine, engine="test", uri=URI.from_path(f2), overrides={})
    assert res2_again.success is True
    assert res2_again.output["cached"] is False


def test_cache_permission_error(tracked_wks_config, tmp_path):
    """Test handling of permission error in cache directory."""

    config = WKSConfig.load()
    # Point cache to a new dir
    cache_dir = tmp_path / "readonly_cache"
    cache_dir.mkdir()
    config.transform.cache.base_dir = str(cache_dir)
    config.save()

    # Make dir read-only
    try:
        cache_dir.chmod(0o500)  # Read/Execute, No Write

        f1 = tmp_path / "f1.txt"
        f1.write_text("content")

        res = run_cmd(cmd_engine, engine="test", uri=URI.from_path(f1), overrides={})
        # Should fail gracefully
        assert res.success is False
        # The error might be about creating cache.json or the cache file itself
        assert "Permission" in str(res.output) or "Access" in str(res.output) or "ReadOnly" in str(res.output)

    finally:
        # Cleanup: restore permissions so pytest can clean up
        cache_dir.chmod(0o700)


def test_database_corruption_recovery(tracked_wks_config, tmp_path):
    """Test recovery when cache file is missing but DB record exists.

    This test verifies that `get_content` enforces the "Database is Sole Authority"
    invariant by pruning stale database records if the corresponding cache file
    is missing from disk.
    """

    f1 = tmp_path / "f1.txt"
    f1.write_text("content")

    # 1. Run once to populate DB and cache
    res = run_cmd(cmd_engine, engine="test", uri=URI.from_path(f1), overrides={})
    checksum = res.output["checksum"]

    # 2. Delete ALL files in cache dir manually to ensure no candidates remain
    config = WKSConfig.load()
    cache_dir = Path(config.transform.cache.base_dir)
    for p in cache_dir.iterdir():
        if p.is_file():
            p.unlink()

    # 3. Trigger cleanup via get_content(checksum)
    # This MUST fail with ValueError because the cache file is gone,
    # and it MUST delete the database record as a side-effect.
    with pytest.raises(ValueError, match=r"Cache file missing|not found"):
        get_content(checksum)

    # 4. Verify DB is cleaned up using public DB class
    with Database(config.database, "transform") as db:
        # Should have 0 records now (pruned by cleanup)
        assert db.get_database()["transform"].count_documents({}) == 0

    # 5. Run again. Should recover by re-transforming.
    res = run_cmd(cmd_engine, engine="test", uri=URI.from_path(f1), overrides={})
    assert res.success is True
    assert res.output["cached"] is False  # Should have re-run because DB was pruned


def test_expand_path_fallback(tracked_wks_config, tmp_path, monkeypatch):
    """Test expand_path logic by invalidating HOME."""
    # This tries to trigger behavior in expand_path
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)  # Windows

    f1 = tmp_path / "f1.txt"
    f1.write_text("content")

    res = run_cmd(cmd_engine, engine="test", uri=URI.from_path(f1), overrides={})
    assert res.success is True


def test_cmd_engine_error_output_schema_conformance(tracked_wks_config, tmp_path):
    """Test that error output conforms to TransformEngineOutput schema.

    This test validates that error outputs from cmd_engine can be parsed
    by the TransformEngineOutput schema model, catching issues like missing
    required fields (e.g., the 'cached' field).
    """
    test_f = tmp_path / "test.txt"
    test_f.touch()

    # Trigger a transform error using the test engine's failure simulation
    result = run_cmd(
        cmd_engine,
        engine="test",
        uri=URI.from_path(test_f),
        overrides={"fail_transform": True},
    )

    assert result.success is False

    # The output must be valid against TransformEngineOutput schema.
    # This will raise ValidationError if required fields are missing.
    TransformEngineOutput.model_validate(result.output)
