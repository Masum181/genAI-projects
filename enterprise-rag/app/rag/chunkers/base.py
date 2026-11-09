"""Shared chunk value type and protocol for chunking strategies."""

from dataclasses import dataclass
from typing import Protocol

from app.rag.extractors.base import ExtractedPage


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A text segment with source location retained for citations."""

    text: str
    page_number: int
    chunk_index: int


class Chunker(Protocol):
    """Contract implemented by fixed-size and semantic chunkers."""

    def chunk(self, pages: list[ExtractedPage]) -> list[TextChunk]:
        """Split ordered page content while retaining source locations."""
