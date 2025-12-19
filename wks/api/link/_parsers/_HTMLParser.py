"""HTML link parser."""

import re
from collections.abc import Iterator

from ._BaseParser import BaseParser, LinkRef

# Simple regex for finding href and src
# Note: This is not a full HTML parser but sufficient for indexing
HREF_PATTERN = re.compile(r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']*)["\']', re.IGNORECASE)
SRC_PATTERN = re.compile(r'src=["\']([^"\']*)["\']', re.IGNORECASE)


class HTMLParser(BaseParser):
    """Parser for HTML files."""

    def parse(self, text: str) -> Iterator[LinkRef]:
        lines = text.splitlines()
        for line_num, line in enumerate(lines, start=1):
            # <a href="...">
            for match in HREF_PATTERN.finditer(line):
                url = match.group(1).strip()
                if not url or url.startswith("#"):
                    continue

                yield LinkRef(
                    line_number=line_num,
                    column_number=match.start() + 1,
                    raw_target=url,
                    link_type="url",
                    alias="",
                    is_embed=False,
                )

            # src="..."
            for match in SRC_PATTERN.finditer(line):
                url = match.group(1).strip()
                if not url:
                    continue

                yield LinkRef(
                    line_number=line_num,
                    column_number=match.start() + 1,
                    raw_target=url,
                    link_type="image",  # or script/embed
                    alias="",
                    is_embed=True,
                )
