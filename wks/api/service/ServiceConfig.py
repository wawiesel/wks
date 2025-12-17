"""Service configuration with Pydantic validation."""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from ._darwin._Data import _Data as _DarwinData
from ._linux._Data import _Data as _LinuxData

# Registry: add new backends here (ONLY place backend types are enumerated)
_BACKEND_REGISTRY: dict[str, type[BaseModel]] = {
    "darwin": _DarwinData,
    "linux": _LinuxData,
}


class ServiceConfig(BaseModel):
    """Service configuration with platform-specific data."""

    _BACKEND_REGISTRY: dict[str, type[BaseModel]] = _BACKEND_REGISTRY

    type: str = Field(..., description="Platform/service manager type")
    data: BaseModel = Field(..., description="Platform-specific configuration data")

    @model_validator(mode="before")
    @classmethod
    def validate_and_populate_data(cls, values: Any) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ValueError(f"service config must be a dict, got {type(values).__name__}")
        daemon_type = values.get("type")
        if not daemon_type:
            raise ValueError("service.type is required")
        # Access module-level registry (single source of truth)
        backend_registry = _BACKEND_REGISTRY
        config_data_class = backend_registry.get(daemon_type)
        if not config_data_class:
            raise ValueError(f"Unknown service type: {daemon_type!r} (supported: {list(backend_registry.keys())})")
        data_dict = values.get("data")
        if data_dict is None:
            raise ValueError("service.data is required")
        # Instantiate platform-specific config class
        values["data"] = config_data_class(**data_dict)
        return values

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Override to properly serialize nested data model."""
        result = super().model_dump(**kwargs)
        # Explicitly serialize the data field since it's typed as BaseModel
        if isinstance(self.data, BaseModel):
            result["data"] = self.data.model_dump(**kwargs)
        return result
