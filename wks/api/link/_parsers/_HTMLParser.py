import re
from collections.abc import Iterator

from ._BaseParser import BaseParser, LinkRef

HREF_PATTERN = re.compile(r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']*)["\']', re.IGNORECASE)
SRC_PATTERN = re.compile(r'src=["\']([^"\']*)["\']', re.IGNORECASE)


class HTMLParser(BaseParser):
    def parse(self, text: str) -> Iterator[LinkRef]:
        lines = text.splitlines()
        for line_num, line in enumerate(lines, start=1):
            for match in HREF_PATTERN.finditer(line):
                if match.lastindex is None or match.lastindex < 1:
                    raise IndexError(f"HREF_PATTERN match missing required group (got {match.lastindex})")
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

            for match in SRC_PATTERN.finditer(line):
                if match.lastindex is None or match.lastindex < 1:
                    raise IndexError(f"SRC_PATTERN match missing required group (got {match.lastindex})")
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
