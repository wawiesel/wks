from collections.abc import Iterator
from contextlib import contextmanager

from ..config.WKSConfig import WKSConfig
from ..database.Database import Database
from ._TransformController import _TransformController


@contextmanager
def _get_controller(wks_config: WKSConfig | None = None) -> Iterator[_TransformController]:
    loaded_config = wks_config or WKSConfig.load()
    transform_config = loaded_config.transform

    with Database(loaded_config.database, "transform") as db:
        yield _TransformController(db, transform_config, transform_config.default_engine)
