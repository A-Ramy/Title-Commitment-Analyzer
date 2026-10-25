"""The numbering check: code, not AI, confirms that every numbered Schedule B-I requirement and B-II exception was
picked up. It reads the PDF text on its own, finds the item numbers printed in each section, and compares them with
what the AI extracted. Gaps go back to the AI; anything still missing is shown on the coverage panel.

Scanned pages have no text, so for them the check falls back to the sequence itself (1, 2, 3 ... with no holes).
"""

from __future__ import annotations

import re

from titleagent.models import EntryOut
from titleagent.pdf import PdfText

# "7.", "7. Payment", "7.Payment" (pypdf drops the space) followed by a capital, a digit ("6.2025 County Taxes"),
# a quote or a bracket
ITEM_LINE = re.compile(r"^\s{0,20}(\d{1,3})\.\s*(?=[A-Z0-9(\"'“\[])")
HEADING = re.compile(r"^\s*SCHEDULE\s+B", re.IGNORECASE)
PART_II = re.compile(r"PART\s*(II|2)\b|\bB\s*[-–—]?\s*II\b|\bBII\b|EXCEPTIONS", re.IGNORECASE)
PART_I = re.compile(r"PART\s*(I|1)\b|\bB\s*[-–—]?\s*I\b|\bBI\b|REQUIREMENTS", re.IGNORECASE)
# A heading line on its own, never a sentence that happens to start with "Schedule A hereof..."
SECTION_END = re.compile(
    r"^(EXHIBIT\s*[\"“”']?[A-Z]?[\"“”']?|SCHEDULE\s+C|SCHEDULE\s+A(\s*\(CONTINUED\))?|LEGAL DESCRIPTION"
    r"|.*PRIVACY (NOTICE|POLICY).*)$",
    re.IGNORECASE,
)


def leading_int(number: str) -> int | None:
    m = re.match(r"\s*(\d+)", number or "")
    return int(m.group(1)) if m else None


def printed_numbers(text: PdfText) -> dict[str, set[int]]:
    """Item numbers printed in the B-I and B-II sections of the text layer: {"B-I": {...}, "B-II": {...}}."""
    found: dict[str, set[int]] = {"B-I": set(), "B-II": set()}
    section: str | None = None
    for page in text.pages:
        lines = page.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if HEADING.match(stripped) and len(stripped) < 70:
                window = " ".join(x.strip() for x in lines[i:i + 3])
                if PART_II.search(window):
                    section = "B-II"
                elif PART_I.search(window):
                    section = "B-I"
                continue  # "SCHEDULE B (Continued)" keeps the current section
            if len(stripped) < 70 and SECTION_END.match(stripped):
                section = None
                continue
            if section:
                m = ITEM_LINE.match(line)
                if m:
                    found[section].add(int(m.group(1)))
    return found


def missing_numbers(extracted: list[EntryOut], printed: set[int]) -> list[int]:
    """Numbers the AI should have extracted but didn't: holes in its own sequence, plus numbers printed in the
    section text just past what it found (a list cut short). Sub-items printed inside an item (a chain of title
    "1. 2. 3.") are already in the sequence, so they never show up here."""
    have = {n for n in (leading_int(e.number) for e in extracted) if n is not None}
    top = max(have, default=0)
    holes = {n for n in range(1, top + 1) if n not in have}
    beyond = {n for n in printed if n not in have and n <= top + 3}
    if not have and printed:  # nothing extracted at all although the text shows items
        beyond = set(printed)
    return sorted(holes | beyond)


def check(text: PdfText | None, requirements: list[EntryOut], exceptions: list[EntryOut]) -> dict[str, list[int]]:
    printed = printed_numbers(text) if text else {"B-I": set(), "B-II": set()}
    return {
        "B-I": missing_numbers(requirements, printed["B-I"]),
        "B-II": missing_numbers(exceptions, printed["B-II"]),
    }
