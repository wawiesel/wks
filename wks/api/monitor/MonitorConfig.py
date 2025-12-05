"""Monitor configuration Pydantic model."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ._FilterConfig import _FilterConfig
from ._PriorityConfig import _PriorityConfig
from ._SyncConfig import _SyncConfig


class MonitorConfig(BaseModel):
    """Monitor configuration loaded from config dict with validation."""

    model_config = ConfigDict(extra="forbid")

    filter: _FilterConfig = Field(default_factory=_FilterConfig)
    priority: _PriorityConfig = Field(default_factory=_PriorityConfig)
    sync: _SyncConfig = Field(...)

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

    def get_rules(self) -> dict[str, list[str]]:
        """Return a dictionary of rule lists."""
        return {
            "include_paths": self.filter.include_paths,
            "exclude_paths": self.filter.exclude_paths,
            "include_dirnames": self.filter.include_dirnames,
            "exclude_dirnames": self.filter.exclude_dirnames,
            "include_globs": self.filter.include_globs,
            "exclude_globs": self.filter.exclude_globs,
        }
