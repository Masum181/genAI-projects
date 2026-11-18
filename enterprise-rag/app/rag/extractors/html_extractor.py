"""HTML content extraction."""

from bs4 import BeautifulSoup
from starlette.concurrency import run_in_threadpool

from app.rag.extractors.base import ExtractedPage


class HTMLExtractor:
    """Extract visible text and the document title from HTML."""

    async def extract(self, content: bytes, *, filename: str) -> list[ExtractedPage]:
        return await run_in_threadpool(self._extract, content, filename)

    @staticmethod
    def _extract(content: bytes, filename: str) -> list[ExtractedPage]:
        soup = BeautifulSoup(content, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else None
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        text = soup.get_text("\n", strip=True)
        if not text:
            return []
        metadata = {"source_filename": filename}
        if title:
            metadata["section_title"] = title
        return [ExtractedPage(text=text, page_number=1, metadata=metadata)]
