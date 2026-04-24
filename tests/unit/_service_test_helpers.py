"""Shared helpers for service unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from wks.api.service.ServiceConfig import ServiceConfig

_DARWIN_SERVICE_DATA = {
    "label": "com.test.wks",
    "keep_alive": True,
    "run_at_load": False,
}


def build_darwin_service_config(*, label: str = "com.test.wks") -> ServiceConfig:
    return ServiceConfig.model_validate({"type": "darwin", "data": {**_DARWIN_SERVICE_DATA, "label": label}})


def patch_backend_import(monkeypatch, backend_name: str, mock_impl: MagicMock) -> None:
    mock_module = MagicMock()
    mock_module._Impl = MagicMock(return_value=mock_impl)
    original_import = __import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if f"{backend_name}._Impl" in name:
            return mock_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", mock_import)


def patch_service_context(monkeypatch, module, mock_service: MagicMock | None = None, *, enter_side_effect=None):
    mock_service_cls = MagicMock()
    if enter_side_effect is not None:
        mock_service_cls.return_value.__enter__.side_effect = enter_side_effect
    else:
        assert mock_service is not None
        mock_service_cls.return_value.__enter__.return_value = mock_service
    monkeypatch.setattr(module, "Service", mock_service_cls)
    return mock_service_cls
