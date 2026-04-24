from ._ENGINES import ENGINES
from .DiffEngine import DiffEngine


def get_engine(name: str) -> DiffEngine | None:
    return ENGINES.get(name)
