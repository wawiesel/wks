"""Markdown URL parser (UNO: single function)."""

import re
from collections.abc import Iterator

from .MarkdownURL import MarkdownURL

MARKDOWN_URL_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def parse_markdown_urls(text: str) -> Iterator[MarkdownURL]:
    """Extract all markdown URLs from text.

    Args:
        text: Markdown content to parse

    Yields:
        MarkdownURL objects for each [text](url) found
    """
    lines = text.splitlines()
    for line_num, line in enumerate(lines, start=1):
        for match in MARKDOWN_URL_PATTERN.finditer(line):
            yield MarkdownURL(
                line_number=line_num,
                column_number=match.start() + 1,
                url=match.group(2).strip(),
                text=match.group(1).strip(),
            )
