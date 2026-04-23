from ._TransformEngine import _TransformEngine


def _get_engine_by_type(engine_type: str) -> _TransformEngine:
    """Get transform engine instance by type.

    Args:
        engine_type: Engine type string (e.g., "docling", "treesitter", "textpass", "imagetext", "binarypass", "null")

    Returns:
        New engine instance

    Raises:
        ValueError: If engine type is unknown
    """
    if engine_type == "docling":
        from ._docling._DoclingEngine import _DoclingEngine

        return _DoclingEngine()
    if engine_type == "treesitter":
        from ._treesitter._TreeSitterEngine import _TreeSitterEngine

        return _TreeSitterEngine()
    if engine_type == "textpass":
        from ._textpass._TextPassEngine import _TextPassEngine

        return _TextPassEngine()
    if engine_type == "imagetext":
        from ._imagetext._ImageTextEngine import _ImageTextEngine

        return _ImageTextEngine()
    if engine_type == "binarypass":
        from ._binarypass._BinaryPassEngine import _BinaryPassEngine

        return _BinaryPassEngine()
    if engine_type == "null":
        from ._NullEngine import _NullEngine

        return _NullEngine()

    raise ValueError(f"Unknown engine type: {engine_type}")
