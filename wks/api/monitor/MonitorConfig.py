"""Monitor configuration Pydantic model."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ._FilterConfig import _FilterConfig
from ._PriorityConfig import _PriorityConfig


class MonitorConfig(BaseModel):
    """Monitor configuration loaded from config dict with validation."""

    model_config = ConfigDict(extra="forbid")

    filter: _FilterConfig = Field(...)
    priority: _PriorityConfig = Field(...)
    database: str = Field(..., description="Collection name (prefix from db config is automatically prepended)")
    max_documents: int = Field(..., ge=0, description="Maximum number of documents in monitor DB")
    min_priority: float = Field(..., ge=0.0, description="Minimum priority for files to be monitored")

    @classmethod
    def from_config_dict(cls, config: dict[str, Any]) -> "MonitorConfig":
        """Load monitor config from config dict."""
        monitor_config_data = config.get("monitor")
        if not monitor_config_data:
            raise KeyError(
                "monitor section is required in config "
                "(found: missing, expected: monitor section with filter, priority, sync)"
            )

        try:
            return cls(**monitor_config_data)
        except ValidationError as e:
            raise e

    @classmethod
    def get_filter_list_names(cls) -> tuple[str, ...]:
        """Return tuple of filter list field names (single source of truth)."""
        return tuple(name for name in _FilterConfig.model_fields if name.startswith(("include", "exclude")))

    def get_rules(self) -> dict[str, list[str]]:
        """Return a dictionary of rule lists."""
        return {name: getattr(self.filter, name) for name in self.get_filter_list_names()}
