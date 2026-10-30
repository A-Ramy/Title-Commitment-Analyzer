"""The Title Commitment Agent's flows without any screen: read the documents, confirm and review, re-run, train, export.
The v2 engine (engine/main.py) runs these; `progress` gets a short line for the page to show while the agent works.
`store` is a firestore_store.FirestoreStore (storage.open_store)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date

from titleagent import duedates, pipeline, prompts, training
from titleagent.exports import INCLUDE, checklist_for, document, tabular
from titleagent.llm import LLM, Usage
from titleagent.models import ActionItem, StructureOut
from titleagent.pdf import is_pdf

Progress = Callable[[str], None] | None
FORMATS = {"csv": "text/csv", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
           "pdf": "application/pdf",
           "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


class FlowError(ValueError):
    """Something the person can fix (wrong file, missing deal); the message is shown as is."""


def _usage_from(d: dict | None) -> Usage:
    u = Usage()
    if d:  # one bill per run: the reading step's tokens count toward the review
        u.input, u.output = d.get("input", 0), d.get("output", 0)
        u.cache_read, u.cache_write = d.get("cache_read", 0), d.get("cache_write", 0)
        u.calls, u.steps = d.get("calls", 0), list(d.get("steps", []))
    return u


def read(store, llm: LLM, commitment: bytes, commitment_name: str, by: str, contract: bytes | None = None,
         contract_name: str = "", update_for: int | None = None, progress: Progress = None) -> dict:
    """Step 1 (Analyze): saves the documents, reads them, runs the numbering check. Returns the draft the confirm
    screen shows: what the agent read, prefilled deal fields and the numbering result."""
    if not is_pdf(commitment):
        raise FlowError("Upload the title commitment as a PDF.")
    if contract and not is_pdf(contract):
        raise FlowError("The purchase contract must be a PDF.")
    existing = store.get_deal(update_for) if update_for else None
    if update_for and not existing:
        raise FlowError("That deal no longer exists.")
    usage = Usage()
    structure, gaps = pipeline.read_documents(llm, pipeline.Documents(commitment, contract), store.active_lessons(),
                                              usage, progress)
    a = structure.schedule_a
    suggested_close = duedates.parse(structure.contract.closing_date) if structure.contract else None
    prefill = {
        "address": (existing or {}).get("address") or a.property_address,
        "state": (existing or {}).get("state") or a.state,
        "deal_type": (existing or {}).get("deal_type") or structure.suggested_deal_type,
        "closing_date": ((existing or {}).get("closing_date") or suggested_close or None),
        "tc": (existing or {}).get("tc") or "",
        "title_company": (existing or {}).get("title_company") or a.issuing_agent,
        "notes": (existing or {}).get("notes") or "",
    }
    if isinstance(prefill["closing_date"], date):
        prefill["closing_date"] = prefill["closing_date"].isoformat()
    return {
        "commitment_doc_id": store.save_document(commitment, commitment_name, "commitment", by=by),
        "contract_doc_id": store.save_document(contract, contract_name, "contract", by=by) if contract else None,
        "structure": structure.model_dump(mode="json"),
        "gaps": gaps,
        "usage": usage.as_dict(),
        "update_for": update_for,
        "prefill": prefill,
        "summary": {
            "requirements": len(structure.requirements), "exceptions": len(structure.exceptions),
            "missing": {k: v for k, v in gaps.items() if v}, "scanned_pages": structure.scanned_pages,
            "commitment_number": a.commitment_number, "commitment_date": a.commitment_date, "county": a.county,
            "vested_owner": a.vested_owner, "deadline_days": a.requirements_deadline_days,
            "proposed_insured": "; ".join(p.proposed_insured for p in a.policies),
        },
    }


def _deal_info(deal: dict) -> pipeline.DealInfo:
    return pipeline.DealInfo(address=deal["address"], state=deal["state"], deal_type=deal["deal_type"],
                             closing_date=deal["closing_date"], tc=deal["tc"], title_company=deal["title_company"],
                             notes=deal["notes"])


def _review(store, llm: LLM, deal_id: int, documents: pipeline.Documents, structure: StructureOut, gaps: dict,
            commitment_doc_id: int, contract_doc_id: int | None, updated_commitment: bool, by: str,
            usage: Usage, progress: Progress) -> int:
    analysis = pipeline.review(llm, documents, structure, _deal_info(store.get_deal(deal_id)),
                               store.active_lessons(), usage, gaps, previous=store.get_items(deal_id),
                               updated_commitment=updated_commitment,
                               offsets=store.get_settings().get("due_offsets"), progress=progress)
    if progress:
        progress("Saving the list")
    return store.save_run(deal_id, analysis, commitment_doc_id, contract_doc_id, updated_commitment, by=by)


def review(store, llm: LLM, draft: dict, fields: dict, by: str, progress: Progress = None) -> int:
    """Step 2 (Confirm → Run Full Review): creates or updates the deal with the confirmed fields, reviews, saves.
    Returns the deal id."""
    structure = StructureOut.model_validate(draft["structure"])
    a = structure.schedule_a
    closing = fields.get("closing_date")
    deal_fields = {
        "address": (fields.get("address") or "").strip(), "state": (fields.get("state") or "").strip().upper()[:2],
        "county": a.county, "deal_type": fields.get("deal_type") or "",
        "closing_date": date.fromisoformat(closing) if isinstance(closing, str) and closing else closing or None,
        "tc": (fields.get("tc") or "").strip(), "title_company": (fields.get("title_company") or "").strip(),
        "commitment_number": a.commitment_number, "notes": (fields.get("notes") or "").strip(),
    }
    update_for = draft.get("update_for")
    if update_for:
        store.update_deal(update_for, **deal_fields)
        deal_id = update_for
    else:
        deal_id = store.create_deal(by=by, **deal_fields)
    store.attach_document(draft["commitment_doc_id"], deal_id)
    if draft.get("contract_doc_id"):
        store.attach_document(draft["contract_doc_id"], deal_id)
    contract = store.get_document(draft["contract_doc_id"]) if draft.get("contract_doc_id") else None
    documents = pipeline.Documents(store.get_document(draft["commitment_doc_id"])["data"],
                                   contract["data"] if contract else None)
    _review(store, llm, deal_id, documents, structure, draft.get("gaps") or {}, draft["commitment_doc_id"],
            draft.get("contract_doc_id"), bool(update_for), by, _usage_from(draft.get("usage")), progress)
    return deal_id


def rerun(store, llm: LLM, deal_id: int, by: str, progress: Progress = None) -> int:
    """Re-run Review: the latest commitment again with the latest lessons; statuses and notes are kept."""
    run = store.latest_run(deal_id)
    if not run:
        raise FlowError("This deal has no review to re-run yet.")
    com = store.get_document(run["commitment_doc_id"])
    con = store.get_document(run["contract_doc_id"]) if run.get("contract_doc_id") else None
    documents = pipeline.Documents(com["data"], con["data"] if con else None)
    structure = StructureOut.model_validate(run["analysis"]["structure"])
    _review(store, llm, deal_id, documents, structure, {}, com["id"], con["id"] if con else None, False, by,
            Usage(), progress)
    return deal_id


def train(store, llm: LLM, data: bytes, filename: str, deal_type: str, name: str, expert: list[str], by: str,
          progress: Progress = None) -> dict:
    """Training: review a worked commitment and compare with the closer's list. Every miss becomes a suggested
    lesson in the Feedback Inbox. Returns the comparison for the page."""
    if not is_pdf(data):
        raise FlowError("Upload the commitment as a PDF.")
    documents = pipeline.Documents(data)
    lessons = store.active_lessons()
    usage = Usage()
    structure, gaps = pipeline.read_documents(llm, documents, lessons, usage, progress)
    analysis = pipeline.review(llm, documents, structure, pipeline.DealInfo(deal_type=deal_type), lessons, usage,
                               gaps, progress=progress)
    blockers = [i for i in analysis.items if i.priority == "blocker"]
    if expert:
        if progress:
            progress("Matching the agent's list to the closer's list")
        result = training.compare(llm, documents, prompts.system_prompt(lessons), expert, analysis.items, usage)
    else:  # clean title: everything the agent marked a blocker is an extra
        result = training.Comparison(matched=[], missed=[], extra=blockers)
    doc_id = store.save_document(data, filename, "training", by=by)
    example_id = store.add_example(name or filename, doc_id, expert, deal_type, by=by)
    store.add_score(example_id, result.recall, len(result.matched), len(result.matched) + len(result.missed),
                    len(lessons))
    for item, lesson in result.missed:
        store.add_feedback("training", item, by=by, detail={"suggested_lesson": lesson, "example_id": example_id})
    return {
        "example_id": example_id, "recall": result.recall, "blockers": len(blockers), "cost_usd": usage.cost,
        "matched": [{"expert": e, "title": i.title, "priority": i.priority} for e, i in result.matched],
        "missed": [{"expert": e, "lesson": lesson} for e, lesson in result.missed],
        "extra": [{"title": i.title, "priority": i.priority, "refs": [s.ref for s in i.sources]}
                  for i in result.extra],
    }


def export(store, deal_id: int, fmt: str, include: str = "all") -> tuple[bytes, str, str]:
    """(file, file name, content type) for Export List."""
    if fmt not in FORMATS:
        raise FlowError(f"Unknown format: {fmt}.")
    if include not in INCLUDE:
        raise FlowError(f"Unknown choice: {include}.")
    deal = store.get_deal(deal_id)
    if not deal:
        raise FlowError("That deal doesn't exist.")
    run = store.latest_run(deal_id)
    checklist = checklist_for(deal, run["analysis"] if run else None, store.get_items(deal_id))
    data = {"csv": tabular.to_csv, "xlsx": tabular.to_xlsx, "pdf": document.to_pdf,
            "docx": document.to_docx}[fmt](checklist, include)
    return data, checklist.filename(fmt, include), FORMATS[fmt]


def missing_item(store, deal_id: int, what: str, where: str, why: str, priority: str, provided_by: str,
                 by: str, add_to_list: bool = True) -> int:
    """Report Missing Item: feedback for the admins and, by default, the item on this deal's list now."""
    if not what.strip():
        raise FlowError("Say what's missing.")
    fid = store.add_feedback("missing", what.strip(), by=by, deal_id=deal_id,
                             detail={"where": where, "why": why, "priority": priority, "provided_by": provided_by})
    if add_to_list:
        item = ActionItem(key=f"fb-{uuid.uuid4().hex[:8]}", priority=priority or "blocker", category="Other",
                          title=what.strip(), action=why.strip() or "Added from feedback.",
                          provided_by=provided_by or "Other", origin="feedback", sources=[{"ref": where or "Feedback"}])
        store.add_item(deal_id, item, by=by)
    return fid
