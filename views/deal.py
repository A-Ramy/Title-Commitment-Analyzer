"""One deal: what has to happen before closing, grouped by priority; the TC updates status, due dates and notes in
place. Exports, Report Missing Item, per-item feedback, re-runs and the deal's documents live here too."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from titleagent import duedates, pipeline
from titleagent.exports import document, google, tabular
from titleagent.models import DONE_STATUSES, PRIORITY_LABEL, STATUSES, ActionItem, Coverage, StructureOut
from ui import html as h
from ui.runs import checklist_for, review_step
from ui.state import get_secrets, get_settings, get_store, who

store = get_store()
deal_id = int(st.query_params.get("id", "0") or 0)
deal = store.get_deal(deal_id) if deal_id else None
if not deal:
    st.title("Deal Not Found")
    st.page_link("views/deals.py", label="See all deals", icon=":material/folder_open:")
    st.stop()

run = store.latest_run(deal_id)
analysis = run["analysis"] if run else None
items = store.get_items(deal_id)
live = [i for i in items if i.change != "removed"]
removed = [i for i in items if i.change == "removed"]


def open_(i: ActionItem) -> bool:
    return i.status not in DONE_STATUSES


# ---------------------------------------------------------------- header
st.title(deal["address"] or f"Deal {deal_id}")
closing = deal["closing_date"]
bits = [deal["deal_type"], f"closing {closing:%b %d, %Y}" if closing else "no closing date", f"TC {deal['tc'] or '—'}",
        deal["title_company"], f"commitment {deal['commitment_number']}" if deal["commitment_number"] else ""]
h.status(" · ".join(h.esc(b) for b in bits if b) + (" · <b>Closed</b>" if deal["status"] != "open" else ""))

if analysis:
    a = analysis["structure"]["schedule_a"]
    committed = duedates.parse(a.get("commitment_date"))
    days = a.get("requirements_deadline_days")
    if committed and days:
        deadline = committed + timedelta(days=int(days))
        if closing and deadline < closing:
            h.box(f"<b>The commitment expires before closing.</b> All requirements must be met by "
                  f"{deadline:%b %d, %Y} ({days} days after the commitment date); closing is {closing:%b %d, %Y}. "
                  "Ask the title company for an updated commitment.", "bad")
        elif deadline < date.today() + timedelta(days=14):
            h.box(f"Requirements must be met by <b>{deadline:%b %d, %Y}</b> ({days} days after the commitment date).",
                  "warn")

# ---------------------------------------------------------------- summary
blockers = [i for i in live if i.priority == "blocker"]
before = [i for i in live if i.priority == "before"]
fyi = [i for i in live if i.priority == "fyi"]
cov = Coverage.model_validate(analysis["coverage"]) if analysis else Coverage()
h.heading("Summary", "1", h.esc(f"{len(live)} items · reviewed {run['created_at']:%b %d, %Y %I:%M %p}" if run else ""))
days_left = (closing - date.today()).days if closing else None
open_blockers, open_before = sum(map(open_, blockers)), sum(map(open_, before))
h.tiles([
    ("Closing Blockers", str(open_blockers), f"{len(blockers)} found · {len(blockers) - open_blockers} cleared",
     "down" if open_blockers else "up"),
    ("Before Closing", str(open_before), f"{len(before)} found · {len(before) - open_before} cleared"),
    ("Review / FYI", str(len(fyi)), "acceptable as is, listed so nothing is hidden"),
    ("Coverage", f"{cov.percent}%", "every numbered item addressed" if cov.complete else "gaps: see below",
     "up" if cov.complete else "down"),
    ("Days To Closing", "—" if days_left is None else str(days_left),
     f"{closing:%b %d}" if closing else "set a closing date",
     "down" if days_left is not None and days_left < 0 else ""),
])


def meter(label: str, done: int, total: int) -> str:
    pct = 100 if total == 0 else int(100 * done / total)
    color = "up" if done == total else "down"
    return (f'<div><div style="display:flex;justify-content:space-between;font-size:13.5px;margin-bottom:5px">'
            f'<span>{h.esc(label)}</span><b class="{color}">{done} / {total}</b></div>'
            f'<div class="meter"><i style="width:{pct}%"></i></div></div>')


if analysis:
    st.html('<div class="box" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px">'
            + meter("B-I requirements addressed", cov.requirements_addressed, cov.requirements_total)
            + meter("B-II exceptions classified", cov.exceptions_addressed, cov.exceptions_total)
            + meter("Pro checklist checks applied", cov.checklist_run, cov.checklist_total) + "</div>")
    if not cov.complete:
        h.box("<b>Check by hand:</b> " + h.esc(", ".join(cov.numbering_gaps + cov.unaddressed))
              + ". The agent could not account for these numbered items.", "bad")
    if cov.unverified_quotes:
        h.box(f"{cov.unverified_quotes} quoted source(s) could not be found word for word on the page they cite "
              "(marked ✗ below). Open the source to check.", "warn")
    for c in analysis.get("corrections") or []:
        h.box(f"<b>Second review:</b> {h.esc(c)}", "warn")

# ---------------------------------------------------------------- actions
checklist = checklist_for(deal, analysis, items)
secrets = get_secrets()
settings = get_settings()
c1, c2, c3, c4 = st.columns([1.2, 1.2, 1, 1])
with c1.popover("Export List", icon=":material/download:", width="stretch"):
    include_fyi = st.toggle("Include Review / FYI items", value=True)
    st.download_button("CSV", tabular.to_csv(checklist, include_fyi), checklist.filename("csv"), "text/csv",
                       width="stretch")
    st.download_button("Excel", tabular.to_xlsx(checklist, include_fyi), checklist.filename("xlsx"),
                       google.XLSX, width="stretch")
    st.download_button("PDF", document.to_pdf(checklist, include_fyi), checklist.filename("pdf"),
                       "application/pdf", width="stretch")
    st.download_button("Word", document.to_docx(checklist, include_fyi), checklist.filename("docx"),
                       google.DOCX, width="stretch")
    st.divider()
    if not secrets.has_google:
        st.caption("Google Sheets / Docs: add the service account in the app's secrets (see README).")
    for kind, label in (("sheet", "Google Sheets"), ("doc", "Google Docs")):
        if st.button(label, width="stretch", disabled=not secrets.has_google, key=f"g_{kind}"):
            try:
                data = (tabular.to_xlsx(checklist, include_fyi) if kind == "sheet"
                        else document.to_docx(checklist, include_fyi))
                link = google.upload(secrets.google_service_account, settings.get("google_folder_id", ""),
                                     f"{checklist.title} · Title Checklist", data, kind)
                st.success(f"Created. [Open it]({link})")
            except google.GoogleExportError as exc:
                st.error(str(exc))


@st.dialog("Report A Missing Item", width="large")
def report_missing() -> None:
    st.caption("Something the agent should have listed. It's added to this deal now and goes to the Feedback Inbox; "
               "once an admin approves it, the agent checks for it on every deal.")
    what = st.text_input("What's missing", placeholder="e.g. Final water bill / utility lien search")
    where = st.text_input("Where in the document (optional)", placeholder="e.g. B-II #10, page 9")
    why = st.text_area("Why it would stop or delay the closing",
                       placeholder="e.g. The city records unpaid water bills as a lien; title won't insure over it.")
    p = st.segmented_control("Priority", ["blocker", "before", "fyi"], default="blocker",
                             format_func=PRIORITY_LABEL.get)
    provided_by = st.text_input("Who has to provide it", value="Seller")
    add_now = st.checkbox("Add it to this deal's list now", value=True)
    if st.button("Send Feedback", type="primary", disabled=not what.strip()):
        store.add_feedback("missing", what.strip(), by=who(), deal_id=deal_id,
                           detail={"where": where, "why": why, "priority": p})
        if add_now:
            item = ActionItem(key=f"fb-{uuid.uuid4().hex[:8]}", priority=p or "blocker",
                              category="Other", title=what.strip(), action=why.strip() or "Added from feedback.",
                              provided_by=provided_by or "Other", origin="feedback",
                              sources=[{"ref": where or "Feedback"}])
            store.add_item(deal_id, item, by=who())
        st.rerun()


if c2.button("Report Missing Item", type="primary", icon=":material/add:", width="stretch"):
    report_missing()

docs = store.list_documents(deal_id)
commitments = [d for d in docs if d["kind"] == "commitment"]
if c3.button("Re-run Review", icon=":material/refresh:", width="stretch", disabled=not (run and commitments),
             help="Reads the latest commitment again with the latest lessons. Statuses and notes are kept."):
    com = store.get_document(run["commitment_doc_id"])
    con = store.get_document(run["contract_doc_id"]) if run.get("contract_doc_id") else None
    documents = pipeline.Documents(com["data"], con["data"] if con else None)
    gaps = {}  # the extraction from the last run is reused; its gaps are on that run's coverage
    if review_step(deal_id, documents, StructureOut.model_validate(analysis["structure"]), gaps, com["id"],
                   con["id"] if con else None, updated_commitment=False):
        st.rerun()
if c4.button("Updated Commitment", icon=":material/upload_file:", width="stretch",
             help="Upload the title company's revised commitment for this deal."):
    st.switch_page("views/analyze.py")

# ---------------------------------------------------------------- the list
view = st.segmented_control("Show", ["All", "Open Only", "Blockers"], default="All", key="deal_filter")
h.heading("Items To Clear Before Closing", "2",
          "Owner is the TC; Provided By is who actually has it. Update Status, Due and Notes below the list.")
STATUS_PILL = {"Open": "p-low", "Ordered": "p-before", "Received": "p-fyi", "Cleared": "p-acc", "Waived": "p-ins"}
PROOF = {True: "✓", False: "✗", None: ""}


def owner(i: ActionItem) -> str:
    return (deal["tc"] or "TC") if i.owner == "TC" else i.owner


def item_table(group: list[ActionItem], start: int) -> str:
    rows = []
    for n, i in enumerate(group, start):
        flag = {"new": '<span class="pill p-low">New</span> ', "removed": '<span class="pill p-ins">Removed</span> '
                }.get(i.change, "")
        src = "<br>".join(f'<span class="src">{h.esc(s.ref)}{f" · p.{s.page}" if s.page else ""} '
                          f'{PROOF[s.verified]}</span>' for s in i.sources)
        cls = "removed" if i.change == "removed" else ("done" if not open_(i) else "")
        rows.append(
            # data-label: on a phone each row becomes a card and the cells show their own labels (ui/brand.css)
            f'<tr class="{cls}"><td class="nw muted num">{n}</td>'
            f'<td class="it">{flag}<b>{h.esc(i.title)}</b><span>{h.esc(i.action)}</span></td>'
            f'<td class="stat" data-label="Status"><span class="pill {STATUS_PILL.get(i.status, "p-ins")}">'
            f'{h.esc(i.status)}</span>{f"<br><small>{h.esc(i.notes)}</small>" if i.notes else ""}</td>'
            f'<td data-label="Provided by">{h.esc(i.provided_by)}<br><small class="muted">Owner: {h.esc(owner(i))}'
            f'</small></td>'
            f'<td class="nw" data-label="Due">'
            f'{h.esc(duedates.parse(i.due_date).strftime("%b %d") if i.due_date else "—")}</td>'
            f'<td class="nw" data-label="Amount">{h.money(i.amount, 2) if i.amount is not None else "—"}</td>'
            f'<td data-label="Source">{src}</td></tr>')
    head = "".join(f"<th>{c}</th>" for c in ("#", "Item & Action Needed", "Status", "Provided By", "Due", "Amount",
                                             "Source"))
    return f'<div class="wrap"><table class="t items"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody>' \
           "</table></div>"


shown_items: list[ActionItem] = []
for p, group in (("blocker", blockers), ("before", before), ("fyi", fyi)):
    if view == "Blockers" and p != "blocker":
        continue
    shown = [i for i in group if open_(i)] if view == "Open Only" else group
    if not shown:
        continue
    st.html(f'<div class="sh"><span class="pill p-{p}">{h.esc(PRIORITY_LABEL[p])}</span><small>{len(shown)} item'
            f'{"s" if len(shown) != 1 else ""}</small></div>' + item_table(shown, len(shown_items) + 1))
    shown_items += shown
if removed and view == "All":
    st.html('<div class="sh"><span class="pill p-ins">Removed by the title company</span><small>in the updated '
            'commitment</small></div>' + item_table(removed, len(shown_items) + 1))
if not live:
    h.box("No items yet. Run the review from Analyze.", "info")

if shown_items:
    st.markdown("**Update Status, Due Dates And Notes**")
    df = pd.DataFrame([{"#": n, "Item": i.title, "Status": i.status, "Due": duedates.parse(i.due_date),
                        "Notes": i.notes} for n, i in enumerate(shown_items, 1)],
                      index=[i.key for i in shown_items])
    edited = st.data_editor(
        df, hide_index=True, key=f"ed_{view}", width="stretch", disabled=["#", "Item"],
        column_config={"#": st.column_config.NumberColumn(width="small"),
                       "Item": st.column_config.TextColumn(width="medium"),
                       "Status": st.column_config.SelectboxColumn(options=STATUSES, required=True, width="small"),
                       "Due": st.column_config.DateColumn(format="MMM D, YYYY", width="medium"),
                       "Notes": st.column_config.TextColumn(width="large")})
    by_key = {i.key: i for i in shown_items}
    changed = False
    for k, row in edited.iterrows():
        i = by_key[k]
        due = row["Due"].isoformat() if isinstance(row["Due"], date) else None
        notes = "" if pd.isna(row["Notes"]) else str(row["Notes"])
        changes = {f: v for f, v in (("status", row["Status"]), ("notes", notes), ("due_date", due))
                   if v != getattr(i, f)}
        if changes:
            store.update_item(deal_id, k, by=who(), **changes)
            changed = True
    if changed:
        st.rerun()

with st.expander("Where each item comes from (exact wording)"):
    for i in live:
        for s in i.sources:
            mark = {True: "✓ found on the page", False: "✗ not found word for word", None: ""}[s.verified]
            st.html(f'<div class="dq"><div class="it"><div><span class="pill p-{i.priority}">'
                    f'{h.esc(PRIORITY_LABEL[i.priority])}</span><br><span class="muted" style="font-size:13px">'
                    f'{h.esc(s.ref)}{f" · p.{s.page}" if s.page else ""}</span></div><div><b>{h.esc(i.title)}</b>'
                    f'<br><span class="muted">{h.esc(i.why)}</span>'
                    f'{f"<br><q>{h.esc(s.quote)}</q>" if s.quote else ""}'
                    f'<br><small class="muted">{mark}</small></div></div></div>')

# ---------------------------------------------------------------- feedback on one item
with st.expander("Feedback on an item"):
    if live:
        keys = [i.key for i in live]
        titles = {i.key: i.title for i in live}
        fk = st.selectbox("Item", keys, format_func=titles.get)
        kind = st.segmented_control("It is…", ["not_needed", "wrong"], default="not_needed",
                                    format_func={"not_needed": "Not Needed", "wrong": "Wrong Info"}.get)
        note = st.text_input("What's wrong (optional)")
        if st.button("Send", key="fb_send"):
            store.add_feedback(kind or "not_needed", f"{titles[fk]}: {note}".strip(": "), by=who(), deal_id=deal_id,
                               item_key=fk, detail={"note": note})
            st.success("Sent to the Feedback Inbox.")

# ---------------------------------------------------------------- deal record
with st.expander("Documents and review history"):
    for d in docs:
        doc = store.get_document(d["id"])
        st.download_button(f"{d['kind'].title()}: {d['filename']} ({d['uploaded_at']:%b %d, %Y})", doc["data"],
                           d["filename"], "application/pdf", key=f"doc{d['id']}")
    for r in store.list_runs(deal_id):
        st.caption(f"Review {r['created_at']:%b %d, %Y %I:%M %p} by {r['created_by']}"
                   f"{' · updated commitment' if r['updated_commitment'] else ''} · AI cost ${r['cost_usd']:.2f}")
    new_status = "closed" if deal["status"] == "open" else "open"
    if st.button("Mark Deal Closed" if new_status == "closed" else "Reopen Deal"):
        store.update_deal(deal_id, status=new_status)
        st.rerun()
