"""WKS CLI package - organized command structure."""

from .main import main
from ..config import load_config

__all__ = ["main", "load_config"]

