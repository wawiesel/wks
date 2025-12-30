from pathlib import Path

from ..config.WKSConfig import WKSConfig
from ._get_mime_type import _get_mime_type


def _select_engine(file_path: Path, override: str | None, config: WKSConfig) -> str:
    """Select engine based on MIME type or override."""
    if override:
        return override

    mime_type = _get_mime_type(file_path)
    cat_config = config.cat

    if hasattr(cat_config, "mime_engines") and cat_config.mime_engines:
        if mime_type in cat_config.mime_engines:
            return cat_config.mime_engines[mime_type]

        base_type = mime_type.split("/")[0] + "/*"
        if base_type in cat_config.mime_engines:
            return cat_config.mime_engines[base_type]

    return cat_config.default_engine or "cat"
