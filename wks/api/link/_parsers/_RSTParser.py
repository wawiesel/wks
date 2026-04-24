import re
from collections.abc import Iterator

from ._BaseParser import BaseParser, LinkRef

RST_LINK_PATTERN = re.compile(r"`([^`<]+)\s+<([^>]+)>`_")
RST_IMAGE_PATTERN = re.compile(r"\.\.\s+image::\s+(.+)")


class RSTParser(BaseParser):
    def parse(self, text: str) -> Iterator[LinkRef]:
        lines = text.splitlines()
        for line_num, line in enumerate(lines, start=1):
            for match in RST_LINK_PATTERN.finditer(line):
                if match.lastindex is None or match.lastindex < 2:
                    raise IndexError(f"RST_LINK_PATTERN match missing required groups (got {match.lastindex})")
                alias = match.group(1).strip()
                url = match.group(2).strip()

                yield LinkRef(
                    line_number=line_num,
                    column_number=match.start() + 1,
                    raw_target=url,
                    link_type="url",
                    alias=alias,
                    is_embed=False,
                )

            image_match = RST_IMAGE_PATTERN.match(line.strip())
            if image_match:
                if image_match.lastindex is None or image_match.lastindex < 1:
                    raise IndexError(f"RST_IMAGE_PATTERN match missing required group (got {image_match.lastindex})")
                url = image_match.group(1).strip()
                yield LinkRef(
                    line_number=line_num,
                    column_number=1,  # approximate
                    raw_target=url,
                    link_type="image",
                    alias="",
                    is_embed=True,
                )
