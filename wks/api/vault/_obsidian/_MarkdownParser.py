"""Markdown link parsing utilities."""

from __future__ import annotations

__all__ = [
    "MarkdownURL",
    "WikiLink",
    "extract_headings",
    "parse_markdown_urls",
    "parse_wikilinks",
]

import re
from collections.abc import Iterator
from dataclasses import dataclass

# Compiled regex patterns for performance
WIKILINK_PATTERN = re.compile(r"(!)?\[\[([^\]]+)\]\]")
MARKDOWN_URL_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


@dataclass(frozen=True)
class WikiLink:
    """A parsed wiki link from markdown."""

    line_number: int
    is_embed: bool
    target: str
    alias: str
    raw_target: str

    @staticmethod
    def split_alias(target: str) -> tuple[str, str]:
        """Split target|alias into components.

        Handles both regular pipes (|) and escaped pipes (\\|) used in tables.
        """
        # Handle escaped pipe (\|) - common in markdown tables
        if "\\|" in target:
            core, alias = target.split("\\|", 1)
            return core.strip(), alias.strip()
        # Handle regular pipe
        if "|" in target:
            core, alias = target.split("|", 1)
            return core.strip(), alias.strip()
        return target.strip(), ""


@dataclass(frozen=True)
class MarkdownURL:
    """A parsed markdown URL from markdown."""

    line_number: int
    url: str
    text: str


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
                is_embed=is_embed,
                target=target,
                alias=alias,
                raw_target=raw_target,
            )


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
                url=match.group(2).strip(),
                text=match.group(1).strip(),
            )


def extract_headings(text: str) -> dict[int, str]:
    """Extract heading for each line number.

    Args:
        text: Markdown content

    Returns:
        Dictionary mapping line numbers to their nearest preceding heading
    """
    headings: dict[int, str] = {}
    current_heading = ""

    for line_num, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            current_heading = stripped.lstrip("#").strip()
        headings[line_num] = current_heading

    return headings
