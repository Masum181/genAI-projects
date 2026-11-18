"""Plain text document extraction."""

from starlette.concurrency import run_in_threadpool

from app.rag.extractors.base import ExtractedPage


class TXTExtractor:
    """Decode a UTF-8 text upload as one source page."""

    async def extract(self, content: bytes, *, filename: str) -> list[ExtractedPage]:
        return await run_in_threadpool(self._extract, content, filename)

    @staticmethod
    def _extract(content: bytes, filename: str) -> list[ExtractedPage]:
        text = content.decode("utf-8-sig").strip()
        return (
            [
                ExtractedPage(
                    text=text,
                    page_number=1,
                    metadata={"source_filename": filename},
                )
            ]
            if text
            else []
        )
