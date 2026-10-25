"""Analyze: upload the commitment (and the contract), confirm the deal details the agent read, run the review."""

from __future__ import annotations

from datetime import date

import streamlit as st

from titleagent import duedates, pipeline
from titleagent.config import DEAL_TYPES, demo_mode
from titleagent.models import StructureOut
from titleagent.pdf import is_pdf
from ui import html as h
from ui.runs import read_step, review_step
from ui.state import get_settings, get_store, who

store = get_store()
settings = get_settings()

st.title("Analyze A Title Commitment")
h.status("Upload the commitment. The agent lists everything that has to happen before this deal can close, "
         "with the page and wording each item comes from.")

pending = st.session_state.get("pending")

if not pending:
    open_deals = store.list_deals(status="open")
    with st.form("upload"):
        c1, c2 = st.columns(2)
        commitment = c1.file_uploader("Title commitment (PDF)", type=["pdf"], key="up_commitment")
        contract = c2.file_uploader("Purchase contract (PDF, optional)", type=["pdf"], key="up_contract",
                                    help="Lets the agent check seller, buyer, price and dates against the commitment.")
        options = [None] + [d["id"] for d in open_deals]
        names = {d["id"]: f"{d['address'] or 'Deal ' + str(d['id'])} · {d['deal_type']}" for d in open_deals}
        update_for = st.selectbox("Is this an updated commitment for a deal already in the app?", options,
                                  format_func=lambda i: "No, a new deal" if i is None else f"Yes: {names[i]}")
        use_sample = st.checkbox("Use the made-up sample commitment", value=False) if demo_mode() else False
        go = st.form_submit_button("Read Documents", type="primary", icon=":material/play_arrow:")

    if go:
        from titleagent import demo

        commitment_bytes = (demo.sample_commitment_pdf() if use_sample
                            else commitment.getvalue() if commitment else None)
        name = "Sample_Commitment.pdf" if use_sample else (commitment.name if commitment else "")
        if not commitment_bytes or not is_pdf(commitment_bytes):
            st.error("Upload the title commitment as a PDF first.")
            st.stop()
        contract_bytes = contract.getvalue() if contract else None
        if contract_bytes and not is_pdf(contract_bytes):
            st.error("The purchase contract must be a PDF.")
            st.stop()
        documents = pipeline.Documents(commitment_bytes, contract_bytes)
        result = read_step(documents)
        if result:
            structure, gaps, usage = result
            st.session_state["pending"] = {
                "commitment_doc_id": store.save_document(commitment_bytes, name, "commitment", by=who()),
                "contract_doc_id": (store.save_document(contract_bytes, contract.name, "contract", by=who())
                                    if contract_bytes else None),
                "structure": structure.model_dump(mode="json"),
                "gaps": gaps,
                "usage": usage,
                "update_for": update_for,
            }
            st.rerun()
    st.stop()

# ---- step 2: confirm what the agent read
structure = StructureOut.model_validate(pending["structure"])
a = structure.schedule_a
gaps = pending["gaps"]
update_for = pending.get("update_for")
existing = store.get_deal(update_for) if update_for else None

h.heading("Confirm The Deal", "1", "Read from the documents. Fix anything that's off, then run the review.")
if any(gaps.values()):
    missing = "; ".join(f"Schedule {k} #{', #'.join(map(str, v))}" for k, v in gaps.items() if v)
    h.box(f"<b>Numbering check:</b> these printed items were not picked up even after a second read: {h.esc(missing)}. "
          "The review will continue and the coverage panel will show them. Check them by hand.", "bad")
else:
    h.box(f"Numbering check passed: {len(structure.requirements)} requirements and {len(structure.exceptions)} "
          f"exceptions, every printed number accounted for."
          + (f" Scanned pages read as images: {', '.join(map(str, structure.scanned_pages))}."
             if structure.scanned_pages else ""), "good")

contract = structure.contract
suggested_close = duedates.parse(contract.closing_date) if contract else None
deal_types = DEAL_TYPES
default_type = (existing or {}).get("deal_type") or structure.suggested_deal_type
tcs = settings.get("tcs") or []

with st.form("confirm"):
    c1, c2 = st.columns(2)
    address = c1.text_input("Property address", value=(existing or {}).get("address") or a.property_address)
    state = c2.text_input("State", value=(existing or {}).get("state") or a.state, max_chars=2)
    c3, c4 = st.columns(2)
    deal_type = c3.selectbox("Deal type", deal_types,
                             index=deal_types.index(default_type) if default_type in deal_types else 0)
    closing = c4.date_input("Closing date", value=(existing or {}).get("closing_date") or suggested_close,
                            min_value=date(2020, 1, 1), format="MM/DD/YYYY")
    c5, c6 = st.columns(2)
    if tcs:
        current = (existing or {}).get("tc")
        tc = c5.selectbox("TC (owns every item)", tcs, index=tcs.index(current) if current in tcs else 0)
    else:
        tc = c5.text_input("TC (owns every item)", value=(existing or {}).get("tc") or who())
    title_company = c6.text_input("Title company", value=(existing or {}).get("title_company") or a.issuing_agent)
    deadline_days = a.requirements_deadline_days
    notes = st.text_area("Notes for the agent (optional)", value=(existing or {}).get("notes") or "",
                         placeholder="e.g. Seller is behind on payments; end buyer is a hard-money borrower.")
    st.html(f'<div class="kv"><span>Commitment <b>{h.esc(a.commitment_number)}</b> dated '
            f'<b>{h.esc(a.commitment_date)}</b>'
            f'{f" · requirements due within <b>{deadline_days} days</b>" if deadline_days else ""}'
            f'</span><span>Vested in <b>{h.esc(a.vested_owner)}</b></span>'
            f'<span>Proposed insured <b>{h.esc("; ".join(p.proposed_insured for p in a.policies))}</b></span></div>')
    b1, b2 = st.columns([1, 1])
    run = b1.form_submit_button("Run Full Review", type="primary", icon=":material/fact_check:")
    cancel = b2.form_submit_button("Start Over")

if cancel:
    st.session_state.pop("pending", None)
    st.rerun()

if run:
    fields = dict(address=address.strip(), state=state.strip().upper(), county=a.county, deal_type=deal_type,
                  closing_date=closing, tc=tc, title_company=title_company.strip(),
                  commitment_number=a.commitment_number, notes=notes.strip())
    if existing:
        deal_id = existing["id"]
        store.update_deal(deal_id, **fields)
    else:
        deal_id = store.create_deal(by=who(), **fields)
    store.attach_document(pending["commitment_doc_id"], deal_id)
    if pending.get("contract_doc_id"):
        store.attach_document(pending["contract_doc_id"], deal_id)
    commitment = store.get_document(pending["commitment_doc_id"])["data"]
    contract_doc = store.get_document(pending["contract_doc_id"]) if pending.get("contract_doc_id") else None
    documents = pipeline.Documents(commitment, contract_doc["data"] if contract_doc else None)
    analysis = review_step(deal_id, documents, structure, gaps, pending["commitment_doc_id"],
                           pending.get("contract_doc_id"), updated_commitment=bool(existing),
                           read_usage=pending.get("usage"))
    if analysis:
        st.session_state.pop("pending", None)
        st.switch_page("views/deal.py", query_params={"id": str(deal_id)})
