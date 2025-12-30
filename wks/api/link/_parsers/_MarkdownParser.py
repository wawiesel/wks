"""Markdown link parser."""

import re
from collections.abc import Iterator

from ._BaseParser import BaseParser, LinkRef

# Compiled regex patterns
WIKILINK_PATTERN = re.compile(r"(!)?\[\[([^\]]+)\]\]")
MARKDOWN_URL_PATTERN = re.compile(r"(!)?\[([^\]]*)\]\(([^)]+)\)")


class MarkdownParser(BaseParser):
    """Parser for Markdown files (Obsidian style and Standard)."""

    def parse(self, text: str) -> Iterator[LinkRef]:
        lines = text.splitlines()
        for line_num, line in enumerate(lines, start=1):
            # 1. WikiLinks: [[Target|Alias]]
            for match in WIKILINK_PATTERN.finditer(line):
                is_embed = bool(match.group(1))
                raw_full = match.group(2).strip()

                # Split alias
                if "\\|" in raw_full:
                    target, alias = raw_full.split("\\|", 1)
                elif "|" in raw_full:
                    target, alias = raw_full.split("|", 1)
                else:
                    target, alias = raw_full, ""

                yield LinkRef(
                    line_number=line_num,
                    column_number=match.start() + 1,
                    raw_target=target.strip(),
                    link_type="wikilink",
                    alias=alias.strip(),
                    is_embed=is_embed,
                )

            # 2. Standard Links: [Alias](Target)
            for match in MARKDOWN_URL_PATTERN.finditer(line):
                is_embed = bool(match.group(1))
                alias = match.group(2).strip()
                url = match.group(3).strip()

                yield LinkRef(
                    line_number=line_num,
                    column_number=match.start() + 1,
                    raw_target=url,
                    link_type="url",
                    alias=alias,
                    is_embed=is_embed,
                )
