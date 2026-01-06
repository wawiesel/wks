from ._binarypass._BinaryPassEngine import _BinaryPassEngine
from ._docling._DoclingEngine import _DoclingEngine
from ._textpass._TextPassEngine import _TextPassEngine
from ._TransformEngine import _TransformEngine
from ._treesitter._TreeSitterEngine import _TreeSitterEngine


def _get_engine_by_type(engine_type: str) -> _TransformEngine:
    """Get transform engine instance by type.

    Args:
        engine_type: Engine type string (e.g., "docling", "treesitter", "textpass", "binarypass")

    Returns:
        New engine instance

    Raises:
        ValueError: If engine type is unknown
    """
    if engine_type == "docling":
        return _DoclingEngine()
    elif engine_type == "treesitter":
        return _TreeSitterEngine()
    elif engine_type == "textpass":
        return _TextPassEngine()
    elif engine_type == "binarypass":
        return _BinaryPassEngine()
    else:
        raise ValueError(f"Unknown engine type: {engine_type}")
