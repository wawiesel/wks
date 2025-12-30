"""Internal hook called after database reset for transform domain."""

from typing import Any

from ._clear_cache import clear_transform_cache


def _post_reset(config: Any) -> None:
    """Hook called after database reset.

    Args:
        config: WKSConfig object
    """
    clear_transform_cache(config)
