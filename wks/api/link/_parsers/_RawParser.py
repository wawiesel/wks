"""Raw text link parser."""

import re
from collections.abc import Iterator

from ._BaseParser import BaseParser, LinkRef

# Simple regex for finding http/https URLs in arbitrary text
# Matches http:// or https:// followed by non-whitespace
URL_PATTERN = re.compile(r"(https?://\S+)")


class RawParser(BaseParser):
    """Parser for raw text files (fallback)."""

    def parse(self, text: str) -> Iterator[LinkRef]:
        lines = text.splitlines()
        for line_num, line in enumerate(lines, start=1):
            for match in URL_PATTERN.finditer(line):
                # Validate match group exists (fail fast if mutated)
                if match.lastindex is None or match.lastindex < 1:
                    raise IndexError(f"URL_PATTERN match missing required group (got {match.lastindex})")
                url = match.group(1).rstrip(",.;:)!]")  # Naive cleanup of trailing punctuation

                yield LinkRef(
                    line_number=line_num,
                    column_number=match.start() + 1,
                    raw_target=url,
                    link_type="url",
                    alias="",
                    is_embed=False,
                )
