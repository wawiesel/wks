"""Daemon configuration with Pydantic validation."""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from ._macos._DaemonConfigData import _DaemonConfigData as _MacOSDaemonConfigData

# Registry: add new backends here (ONLY place backend types are enumerated)
_BACKEND_REGISTRY: dict[str, type[BaseModel]] = {
    "macos": _MacOSDaemonConfigData,
}


class DaemonConfig(BaseModel):
    """Daemon configuration with platform-specific data."""

    _BACKEND_REGISTRY: dict[str, type[BaseModel]] = _BACKEND_REGISTRY

    type: str = Field(..., description="Platform/service manager type")
    data: BaseModel = Field(..., description="Platform-specific configuration data")

    @model_validator(mode="before")
    @classmethod
    def validate_and_populate_data(cls, values: Any) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ValueError(f"daemon config must be a dict, got {type(values).__name__}")
        daemon_type = values.get("type")
        if not daemon_type:
            raise ValueError("daemon.type is required")
        # Access module-level registry (single source of truth)
        backend_registry = _BACKEND_REGISTRY
        config_data_class = backend_registry.get(daemon_type)
        if not config_data_class:
            raise ValueError(f"Unknown daemon type: {daemon_type!r} (supported: {list(platform_registry.keys())})")
        data_dict = values.get("data")
        if data_dict is None:
            raise ValueError("daemon.data is required")
        # Instantiate platform-specific config class
        values["data"] = config_data_class(**data_dict)
        return values

