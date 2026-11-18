"""Tests for PDF text extraction."""

import asyncio

import pymupdf

from app.rag.extractors.pdf_extractor import PDFExtractor


def test_extract_returns_text_pages_with_original_page_numbers() -> None:
    with pymupdf.open() as document:
        first_page = document.new_page()
        first_page.insert_text((72, 72), "First page")
        document.new_page()
        third_page = document.new_page()
        third_page.insert_text((72, 72), "Third page")
        content = document.tobytes()

    pages = asyncio.run(PDFExtractor().extract(content, filename="policy.pdf"))

    assert [(page.text, page.page_number) for page in pages] == [
        ("First page", 1),
        ("Third page", 3),
    ]
    assert all(page.metadata == {"source_filename": "policy.pdf"} for page in pages)
