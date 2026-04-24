import re
from pathlib import Path
from typing import Any

from .DiffConfig import DiffConfig
from .get_engine import get_engine


class DiffController:
    def __init__(self, config: DiffConfig | None = None, transform_controller: Any | None = None):
        self.config = config
        self.transform_controller = transform_controller

    def _validate_engine(self, engine_name: str) -> None:
        if self.config is not None:
            engine_cfg = self.config.engines.get(engine_name)
            if not engine_cfg or not engine_cfg.enabled:
                enabled = sorted(name for name, eng in self.config.engines.items() if eng.enabled)
                enabled_list = ", ".join(enabled) if enabled else "none"
                raise ValueError(f"Unknown engine: {engine_name!r} (enabled engines: {enabled_list})")

    def diff(self, target1: str, target2: str, engine_name: str, options: dict | None = None) -> str:
        file1 = self._resolve_target(target1)
        file2 = self._resolve_target(target2)

        if not file1.exists():
            raise ValueError(f"File not found: {file1}")

        if not file2.exists():
            raise ValueError(f"File not found: {file2}")

        self._validate_engine(engine_name)

        engine = get_engine(engine_name)
        if not engine:
            raise ValueError(f"Unknown engine: {engine_name}")

        options = options or {}
        return engine.diff(file1, file2, options)

    def _resolve_target(self, target: str) -> Path:
        target_str = str(target)

        if re.match(r"^[a-f0-9]{64}$", target_str):
            if not self.transform_controller:
                raise ValueError("TransformController required to resolve checksums")

            cache_dir = self.transform_controller.cache_manager.cache_dir

            cache_file = cache_dir / f"{target_str}.md"
            if not cache_file.exists():
                matches = list(cache_dir.glob(f"{target_str}.*"))
                if matches:
                    cache_file = matches[0]
                else:
                    raise ValueError(f"Cache entry not found: {target_str}")

            return cache_file

        else:
            from wks.api.config.normalize_path import normalize_path

            return normalize_path(target)
