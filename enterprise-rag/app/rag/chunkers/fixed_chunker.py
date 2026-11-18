"""Fixed-size, overlap-aware text chunking."""

import re

from app.rag.chunkers.base import TextChunk
from app.rag.extractors.base import ExtractedPage


class FixedSizeChunker:
    """Split pages into word-bounded chunks while preserving source offsets."""

    def __init__(self, *, chunk_words: int = 900, overlap_words: int = 120) -> None:
        if chunk_words < 1 or not 0 <= overlap_words < chunk_words:
            raise ValueError("Chunk size must be positive and overlap smaller than it")
        self.chunk_words = chunk_words
        self.overlap_words = overlap_words

    def chunk(self, pages: list[ExtractedPage]) -> list[TextChunk]:
        chunks = []
        for page in pages:
            words = list(re.finditer(r"\S+", page.text))
            start = 0
            while start < len(words):
                end = min(start + self.chunk_words, len(words))
                first, last = words[start], words[end - 1]
                chunks.append(
                    TextChunk(
                        text=page.text[first.start() : last.end()],
                        page_number=page.page_number,
                        chunk_index=len(chunks),
                        char_start=first.start(),
                        char_end=last.end(),
                        token_count=end - start,
                    )
                )
                if end == len(words):
                    break
                start = end - self.overlap_words
        return chunks
