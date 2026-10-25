"""Running reviews from the views: progress display, saving, and the checklist used by every export."""

from __future__ import annotations

from datetime import date

import streamlit as st

from titleagent import pipeline
from titleagent.exports import Checklist
from titleagent.llm import AgentError, Usage
from titleagent.models import Analysis, Coverage, StructureOut
from ui.state import get_llm, get_settings, get_store, who


def coverage_line(c: Coverage) -> str:
    return (f"B-I {c.requirements_addressed}/{c.requirements_total} addressed · B-II {c.exceptions_addressed}/"
            f"{c.exceptions_total} classified · {c.checklist_run} pro checks"
            + ("" if c.complete else " · INCOMPLETE: see the app"))


def read_step(documents: pipeline.Documents) -> tuple[StructureOut, dict, dict] | None:
    store = get_store()
    usage = Usage()
    with st.status("Reading the documents…", expanded=True) as s:
        st.write("Reading every page (scanned pages are read as images)…")
        try:
            structure, gaps = pipeline.read_documents(get_llm(), documents, store.active_lessons(), usage)
        except AgentError as exc:
            s.update(label="Could not read the documents", state="error")
            st.error(str(exc))
            return None
        st.write(f"Schedule B-I: {len(structure.requirements)} requirements · Schedule B-II: "
                 f"{len(structure.exceptions)} exceptions")
        if any(gaps.values()):
            st.write("Numbering check: some printed items are still missing (shown on the next step).")
        else:
            st.write("Numbering check: every printed item number was picked up.")
        s.update(label="Documents read", state="complete", expanded=False)
    return structure, gaps, usage.as_dict()


def review_step(deal_id: int, documents: pipeline.Documents, structure: StructureOut, gaps: dict,
                commitment_doc_id: int, contract_doc_id: int | None, updated_commitment: bool,
                read_usage: dict | None = None) -> Analysis | None:
    store = get_store()
    deal = store.get_deal(deal_id)
    info = pipeline.DealInfo(address=deal["address"], state=deal["state"], deal_type=deal["deal_type"],
                             closing_date=deal["closing_date"], tc=deal["tc"], title_company=deal["title_company"],
                             notes=deal["notes"])
    usage = Usage()
    if read_usage:  # one bill per run: carry the reading step's tokens into this run's total
        usage.input, usage.output = read_usage.get("input", 0), read_usage.get("output", 0)
        usage.cache_read, usage.cache_write = read_usage.get("cache_read", 0), read_usage.get("cache_write", 0)
        usage.calls, usage.steps = read_usage.get("calls", 0), list(read_usage.get("steps", []))
    lessons = store.active_lessons()
    with st.status("Reviewing like a title agent…", expanded=True) as s:
        st.write(f"Applying {len(lessons)} team lessons and the professional checklist…")
        st.write("Writing the action list, then a second independent review for anything missing…")
        try:
            analysis = pipeline.review(get_llm(), documents, structure, info, lessons, usage, gaps,
                                       previous=store.get_items(deal_id), updated_commitment=updated_commitment,
                                       offsets=get_settings().get("due_offsets"))
        except AgentError as exc:
            s.update(label="The review did not finish", state="error")
            st.error(str(exc))
            return None
        s.update(label="Review complete", state="complete", expanded=False)
    store.save_run(deal_id, analysis, commitment_doc_id, contract_doc_id, updated_commitment, by=who())
    return analysis


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
