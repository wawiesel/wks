"""Wikilink parser (UNO: single function)."""

import re
from collections.abc import Iterator

from .WikiLink import WikiLink

# Compiled regex patterns for performance
WIKILINK_PATTERN = re.compile(r"(!)?\[\[([^\]]+)\]\]")


def parse_wikilinks(text: str) -> Iterator[WikiLink]:
    """Extract all wiki links from markdown text.

    Args:
        text: Markdown content to parse

    Yields:
        WikiLink objects for each [[...]] or ![[...]] found
    """
    lines = text.splitlines()
    for line_num, line in enumerate(lines, start=1):
        for match in WIKILINK_PATTERN.finditer(line):
            is_embed = bool(match.group(1))
            raw_target = match.group(2).strip()
            target, alias = WikiLink.split_alias(raw_target)
            yield WikiLink(
                line_number=line_num,
                column_number=match.start() + 1,
                is_embed=is_embed,
                target=target,
                alias=alias,
                raw_target=raw_target,
            )
