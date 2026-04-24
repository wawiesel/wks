"""Integration tests for the REST server."""

import pytest
from fastapi.testclient import TestClient

from tests.unit.test_wks_api_search_cmd import _setup_search_config, _write_and_index_search_docs
from wks.api.config.WKSConfig import WKSConfig
from wks.api.search._SearchRuntime import _SEARCH_RUNTIME
from wks.rest.server import create_app
from wks.services import WKSService
from wks.services.status import StatusResponse


def test_rest_server_read_endpoints(monkeypatch, tmp_path):
    """The REST layer should expose thin read endpoints over the shared services."""
    _SEARCH_RUNTIME.reset()
    _setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={"default_index": "main", "indexes": {"main": {"engine": "textpass"}}},
    )
    docs = _write_and_index_search_docs(tmp_path)
    monkeypatch.setattr(
        "wks.services.collect_status",
        lambda: StatusResponse(success=True, message="status", sections={"service": {"running": True}}),
    )

    client = TestClient(create_app(service=WKSService()))

    status_response = client.get("/status")
    search_response = client.get("/search", params={"query": "fission"})
    cat_response = client.get("/cat", params={"target": str(docs[0])})
    sections_response = client.get("/config/sections")

    assert status_response.status_code == 200
    assert status_response.json()["sections"]["service"]["running"] is True
    assert search_response.status_code == 200
    assert search_response.json()["hits"]
    assert cat_response.status_code == 200
    assert "fission" in cat_response.json()["content"].lower()
    assert sections_response.status_code == 200
    assert "monitor" in sections_response.json()["sections"]


def test_rest_server_maps_service_failures(monkeypatch, tmp_path):
    """The REST layer should map shared service failures to HTTP status codes."""
    _SEARCH_RUNTIME.reset()
    _setup_search_config(
        tmp_path,
        monkeypatch,
        index_config={"default_index": "main", "indexes": {"main": {"engine": "textpass"}}},
    )

    client = TestClient(create_app(service=WKSService()))
    response = client.get("/config/missing")

    assert response.status_code == 404
    assert response.json()["detail"]["errors"] == ["Unknown section: missing"]


def test_rest_server_validates_default_config_at_startup(monkeypatch):
    """The standalone REST app should fail at startup when the default config is invalid."""

    def raise_invalid_config():
        raise ValueError("broken config")

    monkeypatch.setattr(WKSConfig, "load", classmethod(lambda cls: raise_invalid_config()))

    with pytest.raises(ValueError, match="broken config"):
        create_app()
