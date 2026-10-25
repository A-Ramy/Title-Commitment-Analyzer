"""Proof for every item: each quote the agent cites must really be on the page it names (or the page next to it,
when an item runs over a page break). Scanned pages have no text layer, so their quotes stay unchecked (None)."""

from __future__ import annotations

import re

from titleagent.models import Source
from titleagent.pdf import SCANNED_WORDS, PdfText

_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", " ": " "})
TOKEN_SHARE = 0.85  # share of the quote's words found on the page that still counts as a match


def norm(s: str) -> str:
    s = s.translate(_QUOTES).lower()
    s = re.sub(r"[^a-z0-9$.,#/\-' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 2]


def found_on(quote: str, page_text: str) -> bool:
    q, p = norm(quote), norm(page_text)
    if not q:
        return False
    if q in p:
        return True
    # pypdf drops or adds spaces around numbers and line breaks; fall back to words
    qt = _tokens(q)
    if len(qt) < 3:
        return q.replace(" ", "") in p.replace(" ", "")
    pt = set(_tokens(p))
    return sum(t in pt for t in qt) / len(qt) >= TOKEN_SHARE


def verify(source: Source, text: PdfText | None) -> Source:
    if not source.quote or source.page is None or text is None:
        return source.model_copy(update={"verified": None})
    page = source.page
    if len(text.page(page).split()) < SCANNED_WORDS:
        return source.model_copy(update={"verified": None})
    for candidate in (page, page + 1, page - 1):
        if found_on(source.quote, text.page(candidate)):
            return source.model_copy(update={"verified": True, "page": candidate})
    return source.model_copy(update={"verified": False})
