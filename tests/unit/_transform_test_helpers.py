"""Shared transform test helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from wks.api.config.WKSConfig import WKSConfig


@contextmanager
def temporary_transform_config(
    *,
    engines: dict,
    default_engine: str | None = None,
) -> Iterator[WKSConfig]:
    """Temporarily replace transform engine settings for one test."""
    config = WKSConfig.load()
    original_engines = config.transform.engines.copy()
    original_default_engine = config.transform.default_engine
    try:
        config.transform.engines = engines
        if default_engine is not None:
            config.transform.default_engine = default_engine
        config.save()
        yield config
    finally:
        config.transform.engines = original_engines
        config.transform.default_engine = original_default_engine
        config.save()
