"""Top-level WKS configuration."""

import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, computed_field

from ..daemon.DaemonConfig import DaemonConfig
from ..database.DatabaseConfig import DatabaseConfig
from ..monitor.MonitorConfig import MonitorConfig
from ..service.ServiceConfig import ServiceConfig
from ..vault.config import VaultConfig


class WKSConfig(BaseModel):
    """Top-level configuration for WKS layers."""

    model_config = ConfigDict(extra="forbid")

    monitor: MonitorConfig
    database: DatabaseConfig
    service: ServiceConfig
    daemon: DaemonConfig
    vault: VaultConfig

    @computed_field
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

        All sections (monitor, database, service, daemon) are required.
        Pydantic validates that all required fields are present.

        Raises:
            ValueError: If config file not found, invalid JSON, or validation error
        """
        path = cls.get_config_path()

        if not path.exists():
            raise ValueError(f"Configuration file not found at {path}")

        try:
            with path.open() as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {path}: {e}") from e

        try:
            # Pydantic validates required fields and constructs nested models automatically
            return cls(**raw)
        except ValidationError as e:
            error_list = e.errors() or [{"msg": str(e), "loc": (), "type": "value_error", "input": None}]
            first = error_list[0]
            error_msg = first.get("msg", str(e))
            loc = first.get("loc", ())
            field = ".".join(str(x) for x in loc) if isinstance(loc, (list, tuple)) else ""
            detail = f"{field}: {error_msg}" if field else error_msg
            raise ValueError(f"Configuration validation error: {detail}") from e

    def to_dict(self) -> dict[str, Any]:
        """Convert WKSConfig instance to a dictionary for serialization."""
        return {
            "monitor": self.monitor.model_dump(),
            "database": self.database.model_dump(),
            "service": self.service.model_dump(),
            "daemon": self.daemon.model_dump(),
            "vault": self.vault.model_dump(),
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
        except Exception as e:
            # Try to clean up temp file if it exists
            # Use suppress for both exists() and unlink() in case of permission errors
            with suppress(Exception):
                if temp_path.exists():
                    temp_path.unlink()
            raise RuntimeError(f"Failed to save config: {e}") from e
