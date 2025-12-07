"""Top-level WKS configuration."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..diff.config import DiffConfig
from ..transform.config import CacheConfig, TransformConfig
from ..vault.config import VaultConfig
from ..db.DbConfig import DbConfig
from ..monitor.MonitorConfig import MonitorConfig
from ..daemon.DaemonConfig import DaemonConfig
from .ConfigError import ConfigError
from .DisplayConfig import DisplayConfig
from .get_config_path import get_config_path
from .MetricsConfig import MetricsConfig


@dataclass
class WKSConfig:
    """Top-level configuration for all WKS layers.

    Diff configuration is optional. When a ``\"diff\"`` section is present in the
    raw config it is validated and attached as a :class:`DiffConfig`. If that
    section is omitted entirely, ``diff`` is left as ``None`` and diff-specific
    features are simply unavailable.
    """

    vault: VaultConfig
    monitor: MonitorConfig
    database: DbConfig
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    diff: DiffConfig | None = None
    transform: TransformConfig = field(
        default_factory=lambda: TransformConfig(
            cache=CacheConfig(location=".wks/transform/cache", max_size_bytes=1073741824),
            engines={},
            database="wks.transform",
        )
    )
    display: DisplayConfig = field(default_factory=DisplayConfig)
    daemon: DaemonConfig | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> "WKSConfig":
        """Load and validate config from file."""
        if path is None:
            path = get_config_path()

        if not path.exists():
            raise ConfigError(f"Configuration file not found at {path}")

        try:
            with path.open() as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file {path}: {e}") from e

        try:
            # Load database config using unified DbConfig
            database = DbConfig(**raw.get("database", {}))

            # Pass the raw config (which contains the 'monitor' key)
            monitor = MonitorConfig.from_config_dict(raw)
            vault = VaultConfig.from_config_dict(raw)
            metrics = MetricsConfig.from_config(raw)
            diff = DiffConfig.from_config_dict(raw) if "diff" in raw else None
            transform = TransformConfig.from_config_dict(raw)
            display = DisplayConfig.from_config(raw)
            daemon = DaemonConfig(**raw.get("daemon", {})) if "daemon" in raw else None

            return cls(
                vault=vault,
                monitor=monitor,
                database=database,
                metrics=metrics,
                diff=diff,
                transform=transform,
                display=display,
                daemon=daemon,
            )
        except (ValidationError, KeyError, ValueError, Exception) as e:
            # Catching Exception to cover VaultConfigError/TransformConfigError if they bubble up
            # Ideally we should import them to catch specifically, but ConfigError wrapper is fine.
            raise ConfigError(f"Configuration validation failed: {e}") from e

    def to_dict(self) -> dict[str, Any]:
        """Convert WKSConfig instance to a dictionary for serialization.

        Handles nested Pydantic models by calling .model_dump().
        """
        data = asdict(self)
        # Handle Pydantic models
        if isinstance(self.monitor, MonitorConfig):
            data["monitor"] = self.monitor.model_dump()
        if isinstance(self.database, DbConfig):
            data["database"] = self.database.model_dump()
        if isinstance(self.daemon, DaemonConfig):
            data["daemon"] = self.daemon.model_dump()
        # Handle other Pydantic models if they exist
        return data

    def save(self, path: Path | None = None) -> None:
        """Save the current configuration to a JSON file.

        Uses atomic write (write to temp file, then rename) to prevent corruption.
        Never deletes the existing config file - only overwrites it atomically.
        """
        if path is None:
            path = get_config_path()

        # Atomic write: write to temp file first, then rename
        # This prevents corruption if the write is interrupted
        temp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with temp_path.open("w") as fh:
                json.dump(self.to_dict(), fh, indent=4)
            # Atomic rename - this is the only operation that modifies the real file
            temp_path.replace(path)
        except Exception:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise
