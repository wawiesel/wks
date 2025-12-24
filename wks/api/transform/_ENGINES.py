"""Transform engines registry."""

from .DoclingEngine import DoclingEngine
from .TestEngine import TestEngine
from .TransformEngine import TransformEngine

# Registry of available engines
ENGINES: dict[str, TransformEngine] = {
    "docling": DoclingEngine(),
    "test": TestEngine(),
}
