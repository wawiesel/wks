"""Unit tests for the public WKSService facade."""

from pathlib import Path

from wks.api.config.WKSConfig import WKSConfig
from wks.services import WKSService
from wks.services.cat import CatResponse
from wks.services.config import ConfigSectionResponse, ConfigSectionsResponse
from wks.services.mv import MoveResponse
from wks.services.search import SearchResponse
from wks.services.status import StatusResponse


def test_wks_service_from_config_loads(monkeypatch, minimal_config_dict):
    """The facade should support explicit construction from WKSConfig.load."""
    config = WKSConfig.model_validate(minimal_config_dict)
    monkeypatch.setattr(WKSConfig, "load", classmethod(lambda cls: config))

    service = WKSService.from_config()

    assert service._config is config


def test_wks_service_methods_delegate(monkeypatch, minimal_config_dict):
    """The facade should delegate each public method to the shared service layer."""
    captured = {}
    config = WKSConfig.model_validate(minimal_config_dict)

    def fake_collect_status():
        return StatusResponse(success=True, message="status", sections={"service": {"running": True}})

    def fake_search_documents(request, *, config=None):
        captured["search"] = (request, config)
        return SearchResponse(
            success=True,
            message="search",
            errors=[],
            warnings=[],
            query=request.query,
            index_name="main",
            search_mode="lexical",
            embedding_model=None,
            hits=[],
            total_chunks=0,
        )

    def fake_read_content(request, *, config=None):
        captured["cat"] = (request, config)
        return CatResponse(
            success=True,
            message="cat",
            errors=[],
            warnings=[],
            content="x",
            target=request.target,
            checksum="abc",
            output_path=None,
        )

    def fake_move_document(request, *, config=None):
        captured["mv"] = (request, config)
        return MoveResponse(
            success=True,
            message="mv",
            errors=[],
            warnings=[],
            source=request.source,
            destination=request.dest,
            database_updated=True,
        )

    def fake_list_config_sections(*, config=None):
        captured["sections"] = config
        return ConfigSectionsResponse(
            success=True,
            message="sections",
            errors=[],
            warnings=[],
            config_path="/tmp/config.json",
            sections=["monitor"],
        )

    def fake_show_config_section(section, *, config=None):
        captured["section"] = (section, config)
        return ConfigSectionResponse(
            success=True,
            message="section",
            errors=[],
            warnings=[],
            config_path="/tmp/config.json",
            section=section,
            content={},
        )

    monkeypatch.setattr("wks.services.collect_status", fake_collect_status)
    monkeypatch.setattr("wks.services.search_documents", fake_search_documents)
    monkeypatch.setattr("wks.services.read_content", fake_read_content)
    monkeypatch.setattr("wks.services.move_document", fake_move_document)
    monkeypatch.setattr("wks.services.list_config_sections", fake_list_config_sections)
    monkeypatch.setattr("wks.services.show_config_section", fake_show_config_section)

    service = WKSService(config=config)

    assert service.status().sections["service"]["running"] is True
    service.search(query="reactor")
    service.cat(target="/tmp/file.txt", output_path=Path("/tmp/out.txt"))
    service.mv(source="/tmp/a.txt", dest="/tmp/b.txt")
    service.config_sections()
    service.config_section("monitor")

    assert captured["search"][0].query == "reactor"
    assert captured["search"][1] is config
    assert captured["cat"][0].target == "/tmp/file.txt"
    assert captured["mv"][0].dest == "/tmp/b.txt"
    assert captured["sections"] is config
    assert captured["section"] == ("monitor", config)
