"""Monitor configuration Pydantic model."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ._PriorityConfig import _PriorityConfig
from ._SyncConfig import _SyncConfig


class MonitorConfig(BaseModel):
    """Monitor configuration loaded from config dict with validation."""

    model_config = ConfigDict(extra="forbid")

    # Filter section - inlined (no special validation needed)
    include_paths: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(default_factory=list)
    include_dirnames: list[str] = Field(default_factory=list)
    exclude_dirnames: list[str] = Field(default_factory=list)
    include_globs: list[str] = Field(default_factory=list)
    exclude_globs: list[str] = Field(default_factory=list)

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

        # Flatten filter section into top-level fields
        flattened = dict(monitor_config_data)
        if "filter" in flattened:
            filter_data = flattened.pop("filter")
            flattened.update(filter_data)

        try:
            return cls(**flattened)
        except ValidationError as e:
            raise e

    @classmethod
    def get_filter_list_names(cls) -> tuple[str, ...]:
        """Return tuple of filter list field names (single source of truth)."""
        return tuple(name for name in cls.model_fields.keys() if name.startswith(("include", "exclude")))

    def get_rules(self) -> dict[str, list[str]]:
        """Return a dictionary of rule lists."""
        return {name: getattr(self, name) for name in self.get_filter_list_names()}
