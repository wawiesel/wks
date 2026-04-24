import copy
from pathlib import Path

from tests.unit.conftest import run_cmd, write_watched_file
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.transform.cmd_engine import cmd_engine
from wks.services.cat import CatRequest, read_content


def test_read_content_by_path(wks_home, minimal_config_dict):
    """The cat service should transform and read content for a path."""
    test_file = write_watched_file(wks_home, name="test.txt", content="Hello Service Cat")

    response = read_content(CatRequest(target=str(test_file)))

    assert response.success is True
    assert response.content == "Hello Service Cat"
    assert response.checksum is not None


def test_read_content_by_checksum(wks_home, minimal_config_dict):
    """The cat service should read cached content by checksum."""
    test_file = write_watched_file(wks_home, name="test.txt", content="Checksum Service Cat")

    transform_result = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(test_file), overrides={})
    assert transform_result.success is True

    response = read_content(CatRequest(target=transform_result.output["checksum"]))

    assert response.success is True
    assert response.content == "Checksum Service Cat"


def test_read_content_reports_missing_file(wks_home):
    """The cat service should return a not_found failure for a missing file."""
    response = read_content(CatRequest(target="/tmp/missing-service-cat"))

    assert response.success is False
    assert response.failure_kind == "not_found"
    assert "File not found" in response.message


def test_read_content_honors_explicit_config(monkeypatch, minimal_config_dict, tmp_path):
    """The cat service should keep both transforms and cache reads on the injected config."""

    def build_config(prefix: str, cache_dir: Path, watch_dir: Path, vault_dir: Path) -> WKSConfig:
        raw = copy.deepcopy(minimal_config_dict)
        raw["database"]["prefix"] = prefix
        raw["transform"]["cache"]["base_dir"] = str(cache_dir)
        raw["monitor"]["filter"]["include_paths"] = [str(watch_dir), str(cache_dir)]
        raw["vault"]["base_dir"] = str(vault_dir)
        return WKSConfig.model_validate(raw)

    watch_dir = tmp_path / "watched"
    watch_dir.mkdir()
    test_file = watch_dir / "test.txt"
    test_file.write_text("Alt config cat content", encoding="utf-8")

    default_config = build_config("wks_default_cat", tmp_path / "default_cache", watch_dir, tmp_path / "default_vault")
    alternate_config = build_config("wks_alt_cat", tmp_path / "alt_cache", watch_dir, tmp_path / "alt_vault")
    monkeypatch.setattr(WKSConfig, "load", classmethod(lambda cls: default_config))

    response = read_content(CatRequest(target=str(test_file)), config=alternate_config)

    assert response.success is True
    assert response.content == "Alt config cat content"
    assert response.checksum is not None

    checksum_response = read_content(CatRequest(target=response.checksum), config=alternate_config)

    assert checksum_response.success is True
    assert checksum_response.content == "Alt config cat content"

    with Database(alternate_config.database, "transform") as database:
        assert database.get_database()["transform"].count_documents({}) == 1

    with Database(default_config.database, "transform") as database:
        assert database.get_database()["transform"].count_documents({}) == 0
