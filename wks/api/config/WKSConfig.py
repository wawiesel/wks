"""Top-level WKS configuration."""

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field

from ..database.DatabaseConfig import DatabaseConfig
from ..monitor.MonitorConfig import MonitorConfig
from ..daemon.DaemonConfig import DaemonConfig


class WKSConfig(BaseModel):
    """Top-level configuration for WKS layers."""

    monitor: MonitorConfig
    database: DatabaseConfig
    daemon: DaemonConfig
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def path(self) -> Path:
        """Path to config file."""
        return self.get_config_path()

    @classmethod
    def get_home_dir(cls) -> Path:
        """Get WKS home directory based on WKS_HOME or default to ~/.wks."""
        wks_home_env = os.environ.get("WKS_HOME")
        if wks_home_env:
            return Path(wks_home_env).expanduser().resolve()
        return Path.home() / ".wks"

    @classmethod
    def get_config_path(cls) -> Path:
        """Get path to config file based on WKS_HOME or default to ~/.wks."""
        return cls.get_home_dir() / "config.json"

    @classmethod
    def load(cls) -> "WKSConfig":
        """Load and validate config from file.

        All sections (monitor, database, daemon) are required.
        Pydantic validates that all required fields are present.
        """
        path = cls.get_config_path()

        if not path.exists():
            raise ValueError(f"Configuration file not found at {path}")

        try:
            with path.open() as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {path}: {e}") from e

        # Pydantic validates required fields and constructs nested models automatically
        return cls(**raw)

    def to_dict(self) -> dict[str, Any]:
        """Convert WKSConfig instance to a dictionary for serialization."""
        return {
            "monitor": self.monitor.model_dump(),
            "database": self.database.model_dump(),
            "daemon": self.daemon.model_dump(),
        }

    def save(self) -> None:
        """Save the current configuration to a JSON file.

        Uses atomic write (write to temp file, then rename) to prevent corruption.
        Never deletes the existing config file - only overwrites it atomically.
        Registers errors in self.errors instead of raising exceptions.
        """
        path = self.get_config_path()
        temp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with temp_path.open("w") as fh:
                json.dump(self.to_dict(), fh, indent=4)
            temp_path.replace(path)
            # Clear any previous save errors on success
            self.errors = [e for e in self.errors if not e.startswith("Save failed:")]
        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            self.errors.append(f"Save failed: {e}")
