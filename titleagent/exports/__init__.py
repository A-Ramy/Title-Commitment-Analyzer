"""Exports of a deal's checklist. Every format carries the same header block and the same columns."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from titleagent.models import PRIORITY_LABEL, ActionItem

COLUMNS = ["#", "Priority", "Category", "Item", "Action Needed", "Owner", "Provided By", "Amount", "Due", "Status",
           "Source", "Notes"]


@dataclass
class Checklist:
    title: str  # the property address
    meta: list[tuple[str, str]]  # header block, in order
    items: list[ActionItem]
    coverage_line: str = ""
    generated: datetime = field(default_factory=datetime.now)

    def visible(self, include_fyi: bool) -> list[ActionItem]:
        return [i for i in self.items if i.change != "removed" and (include_fyi or i.priority != "fyi")]

    def filename(self, ext: str) -> str:
        import re

        base = re.sub(r"[^A-Za-z0-9]+", "_", self.title).strip("_")[:60] or "Title"
        return f"{base}_Title_Checklist.{ext}"


def money(v: float | None) -> str:
    return "" if v is None else f"${v:,.2f}"


def source_text(item: ActionItem) -> str:
    return "; ".join(f"{s.ref}{f' p.{s.page}' if s.page else ''}" for s in item.sources)


def rows(checklist: Checklist, include_fyi: bool) -> list[list[str]]:
    out = []
    for n, i in enumerate(checklist.visible(include_fyi), 1):
        out.append([str(n), PRIORITY_LABEL.get(i.priority, i.priority), i.category, i.title, i.action, i.owner,
                    i.provided_by, money(i.amount), i.due_date or "", i.status, source_text(i), i.notes])
    return out
