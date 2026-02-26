"""Diff engine registry."""

from .Bsdiff3Engine import Bsdiff3Engine
from .MyersEngine import MyersEngine
from .SemanticDiffEngine import SemanticDiffEngine
from .SexpDiffer import SexpDiffer

# Registry of available engines
ENGINES = {
    "bsdiff3": Bsdiff3Engine(),
    "myers": MyersEngine(),
    "semantic": SemanticDiffEngine(),
    "sexp": SexpDiffer(),
}
