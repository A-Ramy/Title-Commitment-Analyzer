"""Exports of a deal's checklist. Every format carries the same header block and the same columns."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from titleagent.models import PRIORITY_LABEL, ActionItem, Coverage

# What an export includes (Export List → Include). Every format takes the same choice.
INCLUDE = {"all": "Everything", "action": "Action items only (no Review / FYI)", "blockers": "Closing Blockers only"}
_PRIORITIES = {"all": ("blocker", "before", "fyi"), "action": ("blocker", "before"), "blockers": ("blocker",)}

COLUMNS = ["#", "Priority", "Category", "Item", "Action Needed", "Owner", "Provided By", "Amount", "Due", "Status",
           "Source", "Notes"]


@dataclass
class Checklist:
    title: str  # the property address
    meta: list[tuple[str, str]]  # header block, in order
    items: list[ActionItem]
    coverage_line: str = ""
    generated: datetime = field(default_factory=lambda: datetime.now(ZoneInfo("America/New_York")))  # the team's time

    @property
    def generated_text(self) -> str:
        return self.generated.strftime("%b %d, %Y %I:%M %p") + (" ET" if self.generated.tzinfo else "")

    def visible(self, include: str = "all") -> list[ActionItem]:
        keep = _PRIORITIES[include]
        return [i for i in self.items if i.change != "removed" and i.priority in keep]

    def heading(self, include: str = "all") -> str:
        """The document's name: a blockers-only export must not pass for the full list."""
        return "Closing Blockers" if include == "blockers" else "Title Checklist"

    def empty_note(self, include: str = "all") -> str:
        """Shown instead of a table when the export has no items (e.g. blockers only on a clean title)."""
        return "No Closing Blockers on this deal." if include == "blockers" else "No items on this list."

    def meta_for(self, include: str = "all") -> list[tuple[str, str]]:
        """The header block, plus a line saying what was left out when the export isn't the whole list."""
        left_out = {"action": "Review / FYI items left out",
                    "blockers": "Before Closing and Review / FYI items left out"}
        if include not in left_out:
            return list(self.meta)
        return [*self.meta, ("Includes", f"{INCLUDE[include]}: {left_out[include]}")]

    def filename(self, ext: str, include: str = "all") -> str:
        """The download's name, stamped with when it was made (as the copy in the Drive folder is)."""
        import re

        base = re.sub(r"[^A-Za-z0-9]+", "_", self.title).strip("_")[:60] or "Title"
        return f"{base}_{self.heading(include).replace(' ', '_')}_{self.generated:%Y-%m-%d_%I%M%p}.{ext}"

    def drive_name(self, include: str = "all", ext: str = "") -> str:
        """The copy's name in the Drive folder: address · heading · date and time (ext for a file kept as is)."""
        return (f"{self.title} · {self.heading(include)} · {self.generated:%Y-%m-%d %I:%M %p}"
                + (" ET" if self.generated.tzinfo else "") + (f".{ext}" if ext else ""))


def money(v: float | None) -> str:
    return "" if v is None else f"${v:,.2f}"


def source_text(item: ActionItem) -> str:
    return "; ".join(f"{s.ref}{f' p.{s.page}' if s.page else ''}" for s in item.sources)


def rows(checklist: Checklist, include: str = "all") -> list[list[str]]:
    out = []
    for n, i in enumerate(checklist.visible(include), 1):
        out.append([str(n), PRIORITY_LABEL.get(i.priority, i.priority), i.category, i.title, i.action, i.owner,
                    i.provided_by, money(i.amount), i.due_date or "", i.status, source_text(i), i.notes])
    return out


def coverage_line(c: Coverage) -> str:
    return (f"B-I {c.requirements_addressed}/{c.requirements_total} addressed · B-II {c.exceptions_addressed}/"
            f"{c.exceptions_total} classified · {c.checklist_run} pro checks"
            + ("" if c.complete else " · INCOMPLETE: see the app"))


def checklist_for(deal: dict, analysis: dict | None, items) -> Checklist:
    a = (analysis or {}).get("structure", {}).get("schedule_a", {})
    insured = "; ".join(f"{p.get('proposed_insured')} (${p['amount']:,.0f})" if p.get("amount") else
                        p.get("proposed_insured", "") for p in a.get("policies", []))
    closing = deal.get("closing_date")
    cov = (analysis or {}).get("coverage")
    meta = [
        ("Deal type", deal.get("deal_type") or ""),
        ("Closing date", closing.strftime("%b %d, %Y") if isinstance(closing, date) else ""),
        ("TC", deal.get("tc") or ""),
        ("Title company", deal.get("title_company") or a.get("issuing_agent", "")),
        ("Commitment #", a.get("commitment_number", "")),
        ("Commitment date", a.get("commitment_date", "")),
        ("Vested owner", a.get("vested_owner", "")),
        ("Proposed insured", insured),
    ]
    return Checklist(title=deal.get("address") or f"Deal {deal['id']}", meta=meta, items=items,
                     coverage_line=coverage_line(Coverage.model_validate(cov)) if cov else "")
