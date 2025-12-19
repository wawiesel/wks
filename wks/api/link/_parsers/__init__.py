"""Link parsers package."""

from pathlib import Path

from ._BaseParser import BaseParser
from ._HTMLParser import HTMLParser
from ._MarkdownParser import MarkdownParser
from ._RawParser import RawParser
from ._RSTParser import RSTParser

_PARSERS: dict[str, type[BaseParser]] = {
    "vault": MarkdownParser,
    "obsidian": MarkdownParser,
    "markdown": MarkdownParser,
    "html": HTMLParser,
    "rst": RSTParser,
    "raw": RawParser,
}

_EXTENSIONS: dict[str, str] = {
    ".md": "markdown",
    ".html": "html",
    ".htm": "html",
    ".rst": "rst",
    ".txt": "raw",
}


def get_parser(parser_name: str | None = None, file_path: Path | None = None) -> BaseParser:
    """Get a parser instance by name or file extension."""

    parser_cls = None

    # 1. By explicit name
    if parser_name:
        parser_cls = _PARSERS.get(parser_name)
        if not parser_cls:
            raise ValueError(f"Unknown parser: {parser_name}")

    # 2. By extension
    elif file_path:
        ext = file_path.suffix.lower()
        parser_name = _EXTENSIONS.get(ext)
        if parser_name:
            parser_cls = _PARSERS.get(parser_name)

    # 3. Fallback to RawParser if no match
    if not parser_cls:
        parser_cls = RawParser

    return parser_cls()
