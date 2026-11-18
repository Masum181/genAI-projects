"""DOCX text and paragraph metadata extraction."""

from io import BytesIO

from docx import Document as WordDocument
from starlette.concurrency import run_in_threadpool

from app.rag.extractors.base import ExtractedPage


class DOCXExtractor:
    """Extract paragraphs and tables from a DOCX upload."""

    async def extract(self, content: bytes, *, filename: str) -> list[ExtractedPage]:
        return await run_in_threadpool(self._extract, content, filename)

    @staticmethod
    def _extract(content: bytes, filename: str) -> list[ExtractedPage]:
        document = WordDocument(BytesIO(content))
        lines = [paragraph.text.strip() for paragraph in document.paragraphs]
        for table in document.tables:
            lines.extend(
                "\t".join(cell.text.strip() for cell in row.cells)
                for row in table.rows
            )
        text = "\n".join(line for line in lines if line)
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
