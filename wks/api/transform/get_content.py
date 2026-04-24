from pathlib import Path

from ..config.WKSConfig import WKSConfig
from ._get_controller import _get_controller


def get_content(target: str, output_path: Path | None = None, *, config: WKSConfig | None = None) -> str:
    with _get_controller(config) as controller:
        return controller.get_content(target, output_path)
