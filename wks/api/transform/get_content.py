"""Get content from transform cache."""

from pathlib import Path

from ._get_controller import _get_controller


def get_content(target: str, output_path: Path | None = None) -> str:
    """Retrieve content for a target (checksum or file path).

    Args:
        target: Checksum (64 hex chars) or file path
        output_path: Optional output file path

    Returns:
        Content as string
    """
    with _get_controller() as controller:
        return controller.get_content(target, output_path)
