"""Unit tests for wks.api.service.Service."""

from unittest.mock import MagicMock

import pytest

from wks.api.service.Service import Service
from wks.api.service.ServiceConfig import ServiceConfig


def test_detect_os():
    """Test OS detection."""
    os_name = Service.detect_os()
    assert os_name in ["darwin", "linux", "windows"]


def test_detect_os_unsupported(monkeypatch):
    """Test unsupported OS raises error."""
    monkeypatch.setattr("platform.system", lambda: "unsupported")

    with pytest.raises(RuntimeError, match="Unsupported operating system"):
        Service.detect_os()


def test_context_manager_unsupported_backend():
    """Test context manager raises for unsupported backend."""
    config = MagicMock(spec=ServiceConfig)
    config.type = "unsupported_backend"

    service = Service(config)
    with pytest.raises(ValueError, match="Unsupported backend type"), service:
        pass


def test_methods_raise_without_context():
    """Test methods raise if not in context."""
    config = MagicMock(spec=ServiceConfig)
    service = Service(config)

    with pytest.raises(RuntimeError, match="not initialized"):
        service.get_service_status()

    with pytest.raises(RuntimeError, match="not initialized"):
        service.install_service()

    with pytest.raises(RuntimeError, match="not initialized"):
        service.uninstall_service()

    with pytest.raises(RuntimeError, match="not initialized"):
        service.start_service()

    with pytest.raises(RuntimeError, match="not initialized"):
        service.stop_service()


def test_validate_backend_type_invalid():
    """Test validate_backend_type with invalid backend."""
    from pydantic import BaseModel

    from wks.api.config.StageResult import StageResult

    class MockOutput(BaseModel):
        errors: list[str]
        warnings: list[str]
        message: str
        running: bool

    result_obj = StageResult(announce="Test", progress_callback=lambda r: iter([]))

    is_valid = Service.validate_backend_type(result_obj, "invalid", MockOutput, "running")

    assert not is_valid
    assert result_obj.success is False
    assert "Unsupported service backend type" in result_obj.output["message"]


def test_start_via_service_success():
    """Test start_via_service returns success."""
    config = MagicMock(spec=ServiceConfig)
    service = Service(config)
    service.start_service = MagicMock(return_value={"success": True, "label": "com.test.service"})  # type: ignore

    result = service.start_via_service()

    assert result.running is True  # type: ignore
    assert "started successfully" in result.message  # type: ignore
    assert result.errors == []  # type: ignore


def test_start_via_service_failure():
    """Test start_via_service handles failure."""
    config = MagicMock(spec=ServiceConfig)
    service = Service(config)
    service.start_service = MagicMock(return_value={"success": False, "error": "Launch failed"})  # type: ignore

    result = service.start_via_service()

    assert result.running is False  # type: ignore
    assert "Error starting service" in result.message  # type: ignore
    assert "Launch failed" in result.errors  # type: ignore


def test_start_via_service_missing_success_field():
    """Test start_via_service raises KeyError on missing success field."""
    config = MagicMock(spec=ServiceConfig)
    service = Service(config)
    service.start_service = MagicMock(return_value={})  # type: ignore

    with pytest.raises(KeyError, match="missing required 'success' field"):
        service.start_via_service()


def test_start_via_service_missing_label_on_success():
    """Test start_via_service raises KeyError on missing label when success=True."""
    config = MagicMock(spec=ServiceConfig)
    service = Service(config)
    service.start_service = MagicMock(return_value={"success": True})  # type: ignore

    with pytest.raises(KeyError, match="missing required 'label' field"):
        service.start_via_service()
