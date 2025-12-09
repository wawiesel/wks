"""Shared helper to load WKS configuration with standard error output."""

from typing import Tuple, Type

from pydantic import BaseModel

from .WKSConfig import WKSConfig


def load_config_with_output(
    section: str, output_cls: Type[BaseModel]
) -> Tuple[WKSConfig | None, dict | None]:
    """Load WKSConfig; on validation/load error return schema-conformant output.

    Args:
        section: config section name ("" for list)
        output_cls: Config*Output model to use

    Returns:
        (config, None) on success; (None, output_dict) on failure
    """
    try:
        config = WKSConfig.load()
        return config, None
    except Exception as e:  # ValidationError or other load issues
        output = output_cls(
            errors=[str(e)],
            warnings=[],
            section=section,
            content={},
            config_path=str(WKSConfig.get_config_path()),
        ).model_dump(mode="python")
        return None, output

