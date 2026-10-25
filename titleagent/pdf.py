"""Reading uploaded PDFs: text per page (for the numbering check and quote verification) and scanned-page detection.

The AI reads the PDF itself (text and page images), so scanned pages are understood; this module only gives the
code its own independent view of the text to check the AI against.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from pypdf import PdfReader

SCANNED_WORDS = 60  # fewer words than this on a page = an image scan (a stamped footer can still carry some text)


@dataclass(frozen=True)
class PdfText:
    pages: list[str]  # index 0 = page 1
    sha256: str

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def scanned_pages(self) -> list[int]:
        return [i + 1 for i, t in enumerate(self.pages) if len(t.split()) < SCANNED_WORDS]

    def page(self, n: int) -> str:
        return self.pages[n - 1] if 1 <= n <= len(self.pages) else ""


def read_pdf(data: bytes) -> PdfText:
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:  # a damaged page still counts; the AI reads its image
            pages.append("")
    return PdfText(pages=pages, sha256=hashlib.sha256(data).hexdigest())


def is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"
