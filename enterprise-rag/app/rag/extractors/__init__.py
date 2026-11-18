"""Format-specific document text extraction components."""

from pathlib import PurePath

from app.rag.extractors.base import ExtractedPage


async def extract_document(content: bytes, *, filename: str) -> list[ExtractedPage]:
    """Select the supported file extractor by its validated extension."""
    suffix = PurePath(filename).suffix.lower()
    if suffix == ".docx":
        from app.rag.extractors.docx_extractor import DOCXExtractor

        extractor_type = DOCXExtractor
    elif suffix in {".htm", ".html"}:
        from app.rag.extractors.html_extractor import HTMLExtractor

        extractor_type = HTMLExtractor
    elif suffix == ".pdf":
        from app.rag.extractors.pdf_extractor import PDFExtractor

        extractor_type = PDFExtractor
    elif suffix == ".txt":
        from app.rag.extractors.txt_extractor import TXTExtractor

        extractor_type = TXTExtractor
    elif suffix == ".xlsx":
        from app.rag.extractors.xlsx_extractor import XLSXExtractor

        extractor_type = XLSXExtractor
    else:
        raise ValueError(f"No document extractor supports {filename!r}")
    return await extractor_type().extract(content, filename=filename)


__all__ = ["ExtractedPage", "extract_document"]
