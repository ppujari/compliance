"""PDF reading utilities for regulatory document extraction."""

from __future__ import annotations
import re
from pathlib import Path


def read_pdf_pages(pdf_path: Path) -> list[str]:
    """Extract text from each page of a PDF. Tries PyMuPDF first, falls back to pdfminer."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path.as_posix())
        pages = [p.get_text("text") for p in doc]
        doc.close()
        return pages
    except Exception:
        try:
            from pdfminer.high_level import extract_text
            from pdfminer.pdfpage import PDFPage
            pages: list[str] = []
            with open(pdf_path, "rb") as f:
                for i, _ in enumerate(PDFPage.get_pages(f)):
                    text = extract_text(pdf_path.as_posix(), page_numbers=[i])
                    pages.append(text or "")
            return pages
        except Exception as e:
            raise RuntimeError(f"Failed to read PDF via PyMuPDF and pdfminer: {e}")


def windowed(pages: list[str], w: int, overlap: int):
    """Yield (start_index, page_list) tuples for sliding window over pages."""
    if w <= 0:
        w = 1
    step = max(1, w - overlap)
    i = 0
    while i < len(pages):
        yield (i, pages[i:i+w])
        i += step


def strip_page_numbers(page_text: str) -> str:
    """Remove bare page numbers from the top of a PDF page."""
    lines = page_text.split("\n")
    # Skip leading blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    # If the first non-blank line is a bare 1-3 digit number, it is a page number
    if lines and re.match(r"^\s*\d{1,3}\s*$", lines[0]):
        lines.pop(0)
    return "\n".join(lines)
