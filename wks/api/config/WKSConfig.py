"""Top-level WKS configuration."""

import json
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ...diff.config import DiffConfig
from ...transform.config import CacheConfig, TransformConfig
from ...vault.config import VaultConfig
from ..db.DbConfig import DbConfig
from ..monitor.MonitorConfig import MonitorConfig
from .DisplayConfig import DisplayConfig
from .MetricsConfig import MetricsConfig
from .ConfigError import ConfigError
from .get_config_path import get_config_path


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
    db: DbConfig
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
            # Load db config using unified DbConfig
            db = DbConfig(**raw.get("db", {}))
            
            # Pass the raw config (which contains the 'monitor' key)
            monitor = MonitorConfig.from_config_dict(raw)
            vault = VaultConfig.from_config_dict(raw)
            metrics = MetricsConfig.from_config(raw)
            diff = DiffConfig.from_config_dict(raw) if "diff" in raw else None
            transform = TransformConfig.from_config_dict(raw)
            display = DisplayConfig.from_config(raw)

            return cls(
                vault=vault,
                monitor=monitor,
                db=db,
                metrics=metrics,
                diff=diff,
                transform=transform,
                display=display,
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
        if isinstance(self.monitor, MonitorConfig):
            data["monitor"] = self.monitor.model_dump()
        # Add other Pydantic models here as they are migrated
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

