"""Diff engine registry."""

from .Bsdiff3Engine import Bsdiff3Engine
from .MyersEngine import MyersEngine

# Registry of available engines
ENGINES = {
    "bsdiff3": Bsdiff3Engine(),
    "myers": MyersEngine(),
    "unified": MyersEngine(),
}
