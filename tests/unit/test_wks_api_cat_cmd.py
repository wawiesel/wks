import subprocess
from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd, write_watched_file
from wks.api.cat.cmd import cmd
from wks.api.config.URI import URI
from wks.api.database.Database import Database
from wks.api.transform._EngineConfig import _EngineConfig
from wks.api.transform.cmd_engine import cmd_engine


@pytest.mark.cat
def test_cmd_by_path(wks_home, minimal_config_dict):
    test_file = write_watched_file(wks_home, name="test.txt", content="Hello Cat")

    res = run_cmd(cmd, target=str(test_file))
    assert res.success is True
    assert res.output["content"] == "Hello Cat"
    assert "target" in res.output


@pytest.mark.cat
def test_cmd_display_messages_include_segmented_full_path(wks_home, minimal_config_dict):
    test_file = write_watched_file(wks_home, name="COR-0017 Code of Record.pdf", content="Hello Cat")
    expected_target = str(test_file)

    stage = cmd(target=str(test_file))

    assert stage.announce == f"Retrieving content for {expected_target}..."
    assert stage.announce_segments == (
        ("Retrieving content for ", None),
        (expected_target, "magenta"),
        ("...", None),
    )

    result = run_cmd(cmd, target=str(test_file))

    assert result.result == "Retrieved content"


@pytest.mark.cat
def test_cmd_by_file_uri(wks_home, minimal_config_dict):
    test_file = write_watched_file(wks_home, name="test-uri.txt", content="Hello URI Cat")

    res = run_cmd(cmd, target=str(URI.from_path(test_file)))
    assert res.success is True
    assert res.output["content"] == "Hello URI Cat"


@pytest.mark.cat
def test_cmd_by_checksum(wks_home, minimal_config_dict):
    test_file = write_watched_file(wks_home, name="test.txt", content="Checksum Cat")

    res_t = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(test_file), overrides={})
    assert res_t.success is True
    checksum = res_t.output["checksum"]

    res = run_cmd(cmd, target=checksum)
    assert res.success is True
    assert res.output["content"] == "Checksum Cat"


@pytest.mark.cat
def test_cmd_to_output_file(wks_home, minimal_config_dict):
    test_file = write_watched_file(wks_home, name="test.txt", content="Output File Content")
    out_file = test_file.parent / "output.md"

    res = run_cmd(cmd, target=str(test_file), output_path=out_file)
    assert res.success is True
    assert out_file.exists()
    assert out_file.read_text() == "Output File Content"


@pytest.mark.cat
def test_cmd_nonexistent_file(wks_home):
    res = run_cmd(cmd, target="/tmp/nonexistent_file_12345")
    assert res.success is False
    assert "File not found" in res.result


@pytest.mark.cat
def test_cmd_nonexistent_checksum(wks_home):
    missing_checksum = "a" * 64
    res = run_cmd(cmd, target=missing_checksum)
    assert res.success is False
    assert "Checksum not found in database" in res.result


@pytest.mark.cat
def test_cmd_stale_cache_record(wks_home, minimal_config_dict):
    test_file = write_watched_file(wks_home, name="stale.txt", content="Stale Content")

    res_t = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(test_file), overrides={})
    assert res_t.success is True
    checksum = res_t.output["checksum"]

    cache_dir = Path(minimal_config_dict["transform"]["cache"]["base_dir"])
    for f in cache_dir.glob(f"{checksum}.*"):
        f.unlink()

    res = run_cmd(cmd, target=checksum)
    assert res.success is False
    assert "Cache file missing" in res.result

    from wks.api.config.WKSConfig import WKSConfig

    config = WKSConfig.load()
    with Database(config.database, "transform") as db:
        assert db.find_one({"checksum": checksum}) is None


@pytest.mark.cat
def test_cmd_engine_override(wks_home, minimal_config_dict, monkeypatch):
    test_file = write_watched_file(wks_home, name="test.txt", content="Engine Override")

    res = run_cmd(cmd, target=str(test_file), engine="textpass")
    assert res.success is True
    assert res.output["content"] == "Engine Override"


@pytest.mark.cat
def test_cmd_mime_engine_selection(wks_home, minimal_config_dict):
    from wks.api.config.WKSConfig import WKSConfig

    config = WKSConfig.load()
    config.cat.mime_engines = {"text/plain": "textpass"}
    config.save()

    test_file = write_watched_file(wks_home, name="test.txt", content="Mime Match")

    res = run_cmd(cmd, target=str(test_file))
    assert res.success is True
    assert res.output["content"] == "Mime Match"


@pytest.mark.cat
def test_cmd_pdf_uses_configured_mime_engine(tracked_wks_config, tmp_path, monkeypatch):
    import wks.api.transform._pdftext._PdfTextEngine as pdftext_module

    config = tracked_wks_config
    config.transform.engines["pdftext"] = _EngineConfig(type="pdftext", data={})
    config.cat.mime_engines = {"application/pdf": "pdftext"}

    test_file = tmp_path / "report.pdf"
    test_file.write_bytes(b"%PDF-1.4\nfake\n")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="Fast PDF text", stderr="")

    monkeypatch.setattr(pdftext_module.subprocess, "run", fake_run)

    res = run_cmd(cmd, target=str(test_file))
    assert res.success is True
    assert res.output["content"] == "Fast PDF text"
