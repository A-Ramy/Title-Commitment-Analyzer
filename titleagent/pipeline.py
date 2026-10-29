"""The review, step by step.

1. read_documents: the AI reports what the commitment (and contract) say; the numbering check confirms every printed
   B-I / B-II number was picked up and sends gaps back once.
2. review: the action list with a disposition for every B-I / B-II number (missing ones go back once), then a second,
   independent pass that only looks for what is missing, then the proof check on every quote, due dates, and the
   carry-over of statuses from the deal's previous list.

Nothing here touches the database; titleagent/flows.py calls it and saves the result.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from titleagent import checklist, compare, numbering, prompts
from titleagent.config import DEAL_TYPES
from titleagent.duedates import due_date
from titleagent.grounding import verify
from titleagent.llm import LLM, Doc, Usage
from titleagent.models import (
    PRIORITY_ORDER,
    ActionItem,
    ActionItemOut,
    ActionsOut,
    Analysis,
    Coverage,
    ReviewOut,
    Source,
    StructureOut,
)
from titleagent.pdf import PdfText, read_pdf


@dataclass
class DealInfo:
    address: str = ""
    state: str = ""
    deal_type: str = ""
    closing_date: date | None = None
    tc: str = ""
    title_company: str = ""
    notes: str = ""

    def describe(self) -> str:
        checks = ", ".join(c.id for c in checklist.for_deal(self.deal_type))
        return "\n".join([
            f"- Property: {self.address or 'see Schedule A'} ({self.state or 'state from Schedule A'})",
            f"- Deal type: {self.deal_type or 'not set'}",
            f"- Closing date: {self.closing_date.isoformat() if self.closing_date else 'not set'}",
            f"- Title company: {self.title_company or 'see commitment'}",
            f"- Team notes: {self.notes or 'none'}",
            f"- Checklist checks that apply to this deal type: {checks}",
        ])


@dataclass
class Documents:
    commitment: bytes
    contract: bytes | None = None

    def docs(self) -> list[Doc]:
        out = [Doc(self.commitment, "Title commitment")]
        if self.contract:
            out.append(Doc(self.contract, "Purchase contract"))
        return out


def _gaps_text(gaps: dict[str, list[int]]) -> str:
    return "; ".join(f"Schedule {k} item(s) {', '.join(map(str, v))}" for k, v in gaps.items() if v)


def _say(progress: Callable[[str], None] | None, message: str) -> None:
    if progress:
        progress(message)


def read_documents(llm: LLM, documents: Documents, lessons: list[str], usage: Usage,
                   progress: Callable[[str], None] | None = None) -> tuple[StructureOut, dict]:
    """Step 1. Returns the extraction and the numbering gaps still left after one retry. `progress` gets a short
    line before each step (the v2 page shows it while the agent works)."""
    _say(progress, "Reading every page (scanned pages are read as images)")
    text = read_pdf(documents.commitment)
    system = prompts.system_prompt(lessons)
    task = prompts.STRUCTURE_TASK.format(deal_types=", ".join(DEAL_TYPES))
    structure = llm.ask(step="structure", system=system, docs=documents.docs(), task=task, schema=StructureOut,
                        usage=usage)
    gaps = numbering.check(text, structure.requirements, structure.exceptions)
    if any(gaps.values()):
        _say(progress, "Numbering check: reading the missing item numbers again")
        retry = task + "\n\n" + prompts.RETRY_TASK.format(missing=_gaps_text(gaps))
        structure = llm.ask(step="structure", system=system, docs=documents.docs(), task=retry, schema=StructureOut,
                            usage=usage)
        gaps = numbering.check(text, structure.requirements, structure.exceptions)
    scanned = sorted(set(structure.scanned_pages) | set(text.scanned_pages))
    structure = structure.model_copy(update={"scanned_pages": scanned})
    return structure, gaps


def _refs(structure: StructureOut) -> list[str]:
    return [f"B-I {e.number}" for e in structure.requirements] + [f"B-II {e.number}" for e in structure.exceptions]


def _canon(ref: str) -> str:
    """'B-I #7', 'BI 7', 'B-I 7.' -> 'B-I 7'."""
    m = re.match(r"\s*(?:schedule\s*)?B\s*[-–—]?\s*(II|I)\b\s*(?:item\s*)?#?\s*([0-9A-Za-z()]+)", ref, re.IGNORECASE)
    if not m:
        return ref.strip()
    return f"B-{m.group(1).upper()} {m.group(2).rstrip('.')}"


def _undisposed(structure: StructureOut, actions: ActionsOut) -> list[str]:
    done = {_canon(d.ref) for d in actions.dispositions}
    return [r for r in _refs(structure) if _canon(r) not in done]


def _origin(item: ActionItemOut, default: str) -> str:
    refs = [s.ref.lower() for s in item.sources]
    if any(r.startswith(("b-i", "b-ii", "sch", "note", "bi", "bii")) for r in refs):
        return default
    if any(r.startswith("contract") for r in refs):
        return "contract"
    if any(r.startswith("checklist") for r in refs):
        return "checklist"
    return default


def _to_item(o: ActionItemOut, origin: str, text: PdfText, closing: date | None, offsets: dict | None) -> ActionItem:
    sources = [verify(Source(ref=_canon(s.ref) if s.ref.upper().startswith("B") else s.ref, page=s.page,
                             quote=s.quote), text) for s in o.sources]
    due = due_date(closing, o.due_rule, offsets)
    item = ActionItem(key="", priority=o.priority, category=o.category, title=o.title, action=o.action,
                      provided_by=o.provided_by, amount=o.amount, due_rule=o.due_rule,
                      due_date=due.isoformat() if due else None, why=o.why, sources=sources,
                      origin=_origin(o, origin))
    return item.model_copy(update={"key": compare.make_key(item)})


def coverage(structure: StructureOut, actions: ActionsOut, gaps: dict, deal_type: str,
             items: list[ActionItem]) -> Coverage:
    done = {_canon(d.ref) for d in actions.dispositions}
    req = [f"B-I {e.number}" for e in structure.requirements]
    exc = [f"B-II {e.number}" for e in structure.exceptions]
    applicable = checklist.for_deal(deal_type)
    return Coverage(
        requirements_total=len(req),
        requirements_addressed=sum(_canon(r) in done for r in req),
        exceptions_total=len(exc),
        exceptions_addressed=sum(_canon(r) in done for r in exc),
        checklist_total=len(applicable),
        checklist_run=len(applicable),  # every applicable check is in the prompt; findings are reported
        unaddressed=[r for r in req + exc if _canon(r) not in done],
        numbering_gaps=[f"{k} {n}" for k, v in gaps.items() for n in v],
        unverified_quotes=sum(1 for i in items for s in i.sources if s.verified is False),
    )


def review(llm: LLM, documents: Documents, structure: StructureOut, deal: DealInfo, lessons: list[str],
           usage: Usage, gaps: dict | None = None, previous: list[ActionItem] | None = None,
           updated_commitment: bool = False, offsets: dict | None = None,
           progress: Callable[[str], None] | None = None) -> Analysis:
    """Steps 2 and 3. `previous` is the deal's current list (statuses carry over); `updated_commitment` marks
    what is new and what the title company removed."""
    text = read_pdf(documents.commitment)
    system = prompts.system_prompt(lessons)
    docs = documents.docs()
    structure_json = json.dumps(structure.model_dump(exclude={"contract"} if not documents.contract else None),
                                indent=1)
    contract_note = ("Cross-check the purchase contract against the commitment: sellers vs vested owner, buyer vs "
                     "proposed insured, price vs policy amount, closing date vs the commitment deadline, assignment "
                     "rights.") if documents.contract else ""
    task = prompts.ACTIONS_TASK.format(deal=deal.describe(), structure=structure_json, contract_note=contract_note)
    _say(progress, f"Writing the action list with {len(lessons)} team lessons and the professional checklist")
    actions = llm.ask(step="actions", system=system, docs=docs, task=task, schema=ActionsOut, usage=usage)
    missing = _undisposed(structure, actions)
    if missing:
        _say(progress, "Giving every numbered item a disposition")
        retry = task + "\n\n" + prompts.ACTIONS_RETRY.format(missing=", ".join(missing))
        actions = llm.ask(step="actions", system=system, docs=docs, task=retry, schema=ActionsOut, usage=usage)

    listed = json.dumps([{"priority": i.priority, "title": i.title, "sources": [s.ref for s in i.sources]}
                         for i in actions.items], indent=1)
    _say(progress, "Second, independent review for anything missing")
    second = llm.ask(step="review", system=system, docs=docs, task=prompts.REVIEW_TASK.format(items=listed),
                     schema=ReviewOut, usage=usage)
    _say(progress, "Checking every quote against its page")

    items = [_to_item(o, "commitment", text, deal.closing_date, offsets) for o in actions.items]
    items += [_to_item(o, "review", text, deal.closing_date, offsets) for o in second.missing_items]
    items = compare.carry_over(items, previous or [], mark_changes=updated_commitment)
    items.sort(key=lambda i: (PRIORITY_ORDER.get(i.priority, 9), i.change == "removed"))

    return Analysis(
        structure=structure,
        items=items,
        dispositions=actions.dispositions,
        checklist_findings=actions.checklist_findings,
        corrections=second.corrections,
        coverage=coverage(structure, actions, gaps or {}, deal.deal_type, items),
        usage=usage.as_dict(),
        lessons_applied=len(lessons),
    )
