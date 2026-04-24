from __future__ import annotations

from pathlib import Path

from wks.api.config.WKSConfig import WKSConfig


def create_watch_dir(wks_home: Path) -> Path:
    watch_dir = Path(f"{wks_home}_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)
    return watch_dir


def include_watch_dir(config: WKSConfig, watch_dir: Path) -> None:
    config.monitor.filter.include_paths.append(str(watch_dir))
    config.save()
