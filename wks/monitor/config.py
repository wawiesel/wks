"""Monitor configuration Pydantic model with validation."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator


class MonitorConfig(BaseModel):
    """Monitor configuration loaded from config dict with validation."""

    include_paths: List[str] = Field(default_factory=list)
    exclude_paths: List[str] = Field(default_factory=list)
    include_dirnames: List[str] = Field(default_factory=list)
    exclude_dirnames: List[str] = Field(default_factory=list)
    include_globs: List[str] = Field(default_factory=list)
    exclude_globs: List[str] = Field(default_factory=list)
    database: str = Field(..., description="Database name in 'database.collection' format")
    managed_directories: Dict[str, int] = Field(default_factory=dict)
    touch_weight: float = Field(0.1, ge=0.001, le=1.0)
    priority: Dict[str, Any] = Field(default_factory=dict)
    max_documents: int = Field(1000000, ge=0)
    prune_interval_secs: float = Field(300.0, gt=0)

    @field_validator("database")
    @classmethod
    def validate_database_format(cls, v: str) -> str:
        """Validate database string is in 'database.collection' format."""
        if "." not in v:
            raise ValueError(
                "Database must be in format 'database.collection' (e.g., 'wks.monitor')"
            )
        parts = v.split(".", 1)
        if not parts[0] or not parts[1]:
            raise ValueError(
                "Database must be in format 'database.collection' with both parts non-empty"
            )
        return v

    @classmethod
    def from_config_dict(cls, config: Dict[str, Any]) -> "MonitorConfig":
        """Load monitor config from config dict.

        Raises:
            KeyError: If monitor section is missing
            PydanticValidationError: If field values are invalid
        """
        monitor_config_data = config.get("monitor")
        if not monitor_config_data:
            raise KeyError(
                "monitor section is required in config "
                "(found: missing, expected: monitor section with include_paths, exclude_paths, etc.)"
            )

        try:
            return cls(**monitor_config_data)
        except ValidationError as e:
            # Re-raise Pydantic's ValidationError directly
            raise e

    def get_rules(self) -> Dict[str, List[str]]:
        """Return a dictionary of rule lists."""
        return {
            "include_paths": self.include_paths,
            "exclude_paths": self.exclude_paths,
            "include_dirnames": self.include_dirnames,
            "exclude_dirnames": self.exclude_dirnames,
            "include_globs": self.include_globs,
            "exclude_globs": self.exclude_globs,
        }

