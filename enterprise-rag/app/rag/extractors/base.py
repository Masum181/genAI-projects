"""Shared result and protocol for document extraction providers."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    """Text and source metadata extracted from one document page."""

    text: str
    page_number: int
    metadata: dict[str, str] = field(default_factory=dict)


class DocumentExtractor(Protocol):
    """Contract implemented by format-specific document extractors."""

    def supports(self, filename: str, content_type: str | None = None) -> bool:
        """Return whether this extractor accepts the indicated document."""

    async def extract(
        self, content: bytes, *, filename: str
    ) -> list[ExtractedPage]:
        """Extract ordered page text and source metadata."""
