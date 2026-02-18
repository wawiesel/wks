"""Sliding window chunker for text content."""

from ._Chunk import _Chunk


class _SlidingWindowChunker:
    """Line-based sliding window chunker with token overlap."""

    def __init__(self, max_tokens: int, overlap_tokens: int):
        self._max_tokens = max_tokens
        self._overlap_tokens = overlap_tokens

    def chunk(self, text: str, uri: str) -> list[_Chunk]:
        """Chunk text into overlapping windows of lines.

        Uses word count as a token proxy. Each window accumulates lines
        up to max_tokens, then backtracks overlap_tokens worth of lines
        before starting the next window.
        """
        lines = text.splitlines(keepends=True)
        if not lines:
            return []

        line_tokens = [len(line.split()) for line in lines]

        chunks: list[_Chunk] = []
        start = 0

        while start < len(lines):
            # Accumulate lines up to budget
            used = 0
            end = start
            while end < len(lines):
                cost = line_tokens[end]
                if used + cost > self._max_tokens and end > start:
                    break
                used += cost
                end += 1

            body = "".join(lines[start:end]).strip()
            if body:
                chunks.append(
                    _Chunk(
                        text=body,
                        uri=uri,
                        chunk_index=len(chunks),
                        tokens=used,
                        is_continuation=(start > 0),
                    )
                )

            if end >= len(lines):
                break

            # Overlap backtrack
            restart = end
            if self._overlap_tokens > 0:
                accum = 0
                pos = end - 1
                while pos > start:
                    if accum + line_tokens[pos] > self._overlap_tokens:
                        break
                    accum += line_tokens[pos]
                    restart = pos
                    pos -= 1

            start = restart

        return chunks
