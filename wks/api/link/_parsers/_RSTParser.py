"""reStructuredText link parser."""

import re
from collections.abc import Iterator

from ._BaseParser import BaseParser, LinkRef

# `Link text <url>`_
RST_LINK_PATTERN = re.compile(r"`([^`<]+)\s+<([^>]+)>`_")
# .. image:: url
RST_IMAGE_PATTERN = re.compile(r"\.\.\s+image::\s+(.+)")


class RSTParser(BaseParser):
    """Parser for reStructuredText files."""

    def parse(self, text: str) -> Iterator[LinkRef]:
        lines = text.splitlines()
        for line_num, line in enumerate(lines, start=1):
            # `Text <URL>`_
            for match in RST_LINK_PATTERN.finditer(line):
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

            # .. image:: URL
            # .. image:: URL
            image_match = RST_IMAGE_PATTERN.match(line.strip())
            if image_match:
                url = image_match.group(1).strip()
                yield LinkRef(
                    line_number=line_num,
                    column_number=1,  # approximate
                    raw_target=url,
                    link_type="image",
                    alias="",
                    is_embed=True,
                )
