"""Monitor configuration Pydantic model."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class FilterConfig(BaseModel):
    """Filter configuration for include/exclude rules."""

    include_paths: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(default_factory=list)
    include_dirnames: list[str] = Field(default_factory=list)
    exclude_dirnames: list[str] = Field(default_factory=list)
    include_globs: list[str] = Field(default_factory=list)
    exclude_globs: list[str] = Field(default_factory=list)


class PriorityWeightsConfig(BaseModel):
    """Priority weights configuration."""

    depth_multiplier: float = Field(0.9, gt=0.0)
    underscore_multiplier: float = Field(0.5, gt=0.0)
    only_underscore_multiplier: float = Field(0.1, gt=0.0)
    extension_weights: dict[str, float] = Field(default_factory=dict)


class PriorityConfig(BaseModel):
    """Priority configuration."""

    dirs: dict[str, float] = Field(default_factory=dict)
    weights: PriorityWeightsConfig = Field(default_factory=PriorityWeightsConfig)


class SyncConfig(BaseModel):
    """Sync configuration."""

    database: str = Field(..., description="Database name in 'database.collection' format")
    max_documents: int = Field(1000000, ge=0)
    min_priority: float = Field(0.0, ge=0.0)
    prune_interval_secs: float = Field(300.0, gt=0)

    @field_validator("database")
    @classmethod
    def validate_database_format(cls, v: str) -> str:
        """Validate database string is in 'database.collection' format."""
        if "." not in v:
            raise ValueError("Database must be in format 'database.collection' (e.g., 'wks.monitor')")
        parts = v.split(".", 1)
        if not parts[0] or not parts[1]:
            raise ValueError("Database must be in format 'database.collection' with both parts non-empty")
        return v


class MonitorConfig(BaseModel):
    """Monitor configuration loaded from config dict with validation."""

    model_config = ConfigDict(extra="forbid")

    filter: FilterConfig = Field(default_factory=FilterConfig)
    priority: PriorityConfig = Field(default_factory=PriorityConfig)
    sync: SyncConfig = Field(...)

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

    # Compatibility properties for backward compatibility during migration
    @property
    def include_paths(self) -> list[str]:
        """Compatibility property for include_paths."""
        return self.filter.include_paths

    @property
    def exclude_paths(self) -> list[str]:
        """Compatibility property for exclude_paths."""
        return self.filter.exclude_paths

    @property
    def include_dirnames(self) -> list[str]:
        """Compatibility property for include_dirnames."""
        return self.filter.include_dirnames

    @property
    def exclude_dirnames(self) -> list[str]:
        """Compatibility property for exclude_dirnames."""
        return self.filter.exclude_dirnames

    @property
    def include_globs(self) -> list[str]:
        """Compatibility property for include_globs."""
        return self.filter.include_globs

    @property
    def exclude_globs(self) -> list[str]:
        """Compatibility property for exclude_globs."""
        return self.filter.exclude_globs

    @property
    def database(self) -> str:
        """Compatibility property for database."""
        return self.sync.database

    @property
    def max_documents(self) -> int:
        """Compatibility property for max_documents."""
        return self.sync.max_documents

    @property
    def min_priority(self) -> float:
        """Compatibility property for min_priority."""
        return self.sync.min_priority

    @property
    def prune_interval_secs(self) -> float:
        """Compatibility property for prune_interval_secs."""
        return self.sync.prune_interval_secs

    @property
    def managed_directories(self) -> dict[str, float]:
        """Compatibility property for managed_directories (maps to priority.dirs)."""
        return self.priority.dirs
