"""XLSX worksheet and cell content extraction."""

from io import BytesIO

from openpyxl import load_workbook
from starlette.concurrency import run_in_threadpool

from app.rag.extractors.base import ExtractedPage


class XLSXExtractor:
    """Extract non-empty rows from each worksheet in an XLSX upload."""

    async def extract(self, content: bytes, *, filename: str) -> list[ExtractedPage]:
        return await run_in_threadpool(self._extract, content, filename)

    @staticmethod
    def _extract(content: bytes, filename: str) -> list[ExtractedPage]:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        try:
            pages = []
            for page_number, worksheet in enumerate(workbook.worksheets, start=1):
                rows = [
                    "\t".join("" if value is None else str(value) for value in row)
                    for row in worksheet.iter_rows(values_only=True)
                ]
                text = "\n".join(row for row in rows if row.strip())
                if text:
                    pages.append(
                        ExtractedPage(
                            text=text,
                            page_number=page_number,
                            metadata={
                                "section_title": worksheet.title,
                                "source_filename": filename,
                            },
                        )
                    )
            return pages
        finally:
            workbook.close()
