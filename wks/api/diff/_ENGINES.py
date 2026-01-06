"""Diff engine registry."""

from .AstEngine import AstEngine
from .Bsdiff4Engine import Bsdiff4Engine
from .MyersEngine import MyersEngine

# Registry of available engines
ENGINES = {
    "ast": AstEngine(),
    "bsdiff4": Bsdiff4Engine(),
    "myers": MyersEngine(),
}
