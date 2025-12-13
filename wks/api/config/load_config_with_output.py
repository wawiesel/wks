"""Load WKS config and return schema-conformant error output on failure."""

from pydantic import BaseModel

from .WKSConfig import WKSConfig


def load_config_with_output(section: str, output_cls: type[BaseModel]) -> tuple[WKSConfig | None, dict | None]:
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
