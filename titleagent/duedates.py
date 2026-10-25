"""Due dates from the closing date: each kind of item is due a set number of days before closing (Settings), and a
date that lands on a weekend moves back to the Friday before."""

from __future__ import annotations

from datetime import date, timedelta

from titleagent.config import DEFAULT_SETTINGS


def due_date(closing: date | None, rule: str, offsets: dict | None = None) -> date | None:
    offsets = offsets or DEFAULT_SETTINGS["due_offsets"]
    if closing is None or rule not in offsets:
        return None
    d = closing - timedelta(days=int(offsets[rule]))
    while d.weekday() >= 5:  # Saturday 5, Sunday 6
        d -= timedelta(days=1)
    return d


def parse(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None
