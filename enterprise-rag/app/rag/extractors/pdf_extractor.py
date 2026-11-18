"""PDF text and page metadata extraction."""

import pymupdf
from starlette.concurrency import run_in_threadpool

from app.rag.extractors.base import ExtractedPage


class PDFExtractor:
    """Extract ordered text pages from a PDF upload."""

    async def extract(self, content: bytes, *, filename: str) -> list[ExtractedPage]:
        return await run_in_threadpool(self._extract, content, filename)

    @staticmethod
    def _extract(content: bytes, filename: str) -> list[ExtractedPage]:
        with pymupdf.open(stream=content, filetype="pdf") as document:
            return [
                ExtractedPage(
                    text=text,
                    page_number=page_number,
                    metadata={"source_filename": filename},
                )
                for page_number, page in enumerate(document, start=1)
                if (text := page.get_text("text").strip())
            ]
