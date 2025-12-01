"""Diff controller with business logic."""

import re
from pathlib import Path
from typing import Optional, Any, Dict

from .engines import get_engine
from .config import DiffConfig


class DiffController:
    """Business logic for diff operations."""

    def __init__(self, config: Optional[DiffConfig] = None, transform_controller: Optional[Any] = None):
        """Initialize diff controller.

        Args:
            config: Optional DiffConfig with engine configuration. When provided,
                engine names are validated against this configuration.
            transform_controller: Optional TransformController for resolving checksums
        """
        self.config = config
        self.transform_controller = transform_controller

    def diff(
        self,
        target1: str,
        target2: str,
        engine_name: str,
        options: Optional[dict] = None
    ) -> str:
        """Compute diff between two targets (files or checksums).

        Args:
            target1: First file path or cache checksum
            target2: Second file path or cache checksum
            engine_name: Diff engine name (e.g., "bsdiff3", "myers")
            options: Engine-specific options

        Returns:
            Diff output as string

        Raises:
            ValueError: If files don't exist or engine not found
            RuntimeError: If diff operation fails
        """
        file1 = self._resolve_target(target1)
        file2 = self._resolve_target(target2)

        if not file1.exists():
            raise ValueError(f"File not found: {file1}")

        if not file2.exists():
            raise ValueError(f"File not found: {file2}")

        # If configuration is available, validate the engine name against it.
        if self.config is not None:
            engine_cfg = self.config.engines.get(engine_name)
            if not engine_cfg or not engine_cfg.enabled:
                enabled = sorted(
                    name for name, eng in self.config.engines.items() if eng.enabled
                )
                enabled_list = ", ".join(enabled) if enabled else "none"
                raise ValueError(
                    f"Unknown engine: {engine_name!r} "
                    f"(enabled engines: {enabled_list})"
                )

        # Get engine implementation
        engine = get_engine(engine_name)
        if not engine:
            raise ValueError(f"Unknown engine: {engine_name}")

        # Perform diff
        options = options or {}
        return engine.diff(file1, file2, options)

    def _resolve_target(self, target: str) -> Path:
        """Resolve target to a file path.

        Args:
            target: File path or checksum

        Returns:
            Path object
        """
        # Convert to string if it's a Path
        target_str = str(target)

        # Check if target is a checksum
        if re.match(r'^[a-f0-9]{64}$', target_str):
            if not self.transform_controller:
                raise ValueError("TransformController required to resolve checksums")
            
            # Use transform controller to find cache file
            cache_dir = self.transform_controller.cache_manager.cache_dir
            
            # Try to find file with any extension
            cache_file = cache_dir / f"{target_str}.md"
            if not cache_file.exists():
                 matches = list(cache_dir.glob(f"{target_str}.*"))
                 if matches:
                     cache_file = matches[0]
                 else:
                     raise ValueError(f"Cache entry not found: {target_str}")
            
            return cache_file
            
        else:
            # Assume file path
            return Path(target).resolve()
