from ._docling._DoclingEngine import _DoclingEngine
from ._treesitter._TreeSitterEngine import _TreeSitterEngine
from ._testengine._TestEngine import _TestEngine
from ._TransformEngine import _TransformEngine


def _get_engine_by_type(engine_type: str) -> _TransformEngine:
    """Get transform engine instance by type.

    Args:
        engine_type: Engine type string (e.g., "docling")

    Returns:
        New engine instance

    Raises:
        ValueError: If engine type is unknown
    """
    if engine_type == "docling":
        return _DoclingEngine()
    elif engine_type == "test":
        return _TestEngine()
    elif engine_type == "treesitter":
        return _TreeSitterEngine()
    else:
        raise ValueError(f"Unknown engine type: {engine_type}")
