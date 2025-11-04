"""Thin wrapper around Jinja2 for rendering CLI outputs."""

from __future__ import annotations

from typing import Any, Dict

from jinja2 import Environment, BaseLoader, StrictUndefined

_ENV = Environment(loader=BaseLoader(), trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)


def render_template(template: str, context: Dict[str, Any]) -> str:
    tmpl = _ENV.from_string(template)
    return tmpl.render(**context)
