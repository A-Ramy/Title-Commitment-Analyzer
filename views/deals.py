"""Deals: every commitment the agent has reviewed, searchable, with open blockers and what's due."""

from __future__ import annotations

from datetime import date

import streamlit as st

from titleagent.models import DONE_STATUSES
from ui import html as h
from ui.state import get_store

store = get_store()
st.title("Deals")
h.status("Every commitment the agent has reviewed. Open a deal to work its list or upload an updated commitment.")

c1, c2 = st.columns([2, 1])
q = c1.text_input("Search", placeholder="Address, TC, title company, commitment #", label_visibility="collapsed")
status = c2.segmented_control("Status", ["open", "closed", "all"], default="open", label_visibility="collapsed",
                              format_func=str.title)
deals = store.list_deals(None if status in (None, "all") else status)
if q:
    ql = q.lower()
    deals = [d for d in deals if ql in " ".join(str(d.get(k) or "") for k in
                                                ("address", "tc", "title_company", "commitment_number",
                                                 "deal_type")).lower()]
items = store.open_items_by_deal() if status != "closed" else {}

if not deals:
    h.box("No deals here yet. Upload a commitment on Analyze.", "info")
    st.stop()

today = date.today().isoformat()
for d in deals:
    its = [i for i in items.get(d["id"], []) if i.status not in DONE_STATUSES and i.change != "removed"]
    blockers = sum(1 for i in its if i.priority == "blocker")
    overdue = sum(1 for i in its if i.due_date and i.due_date < today)
    with st.container(key=f"card-deal-{d['id']}"):
        a, b = st.columns([3, 1])
        closing = f"closing {d['closing_date']:%b %d, %Y}" if d["closing_date"] else "no closing date"
        a.markdown(f"**{d['address'] or 'Deal ' + str(d['id'])}**  \n{d['deal_type']} · {closing}")
        counts = (f"{blockers} open blocker{'s' if blockers != 1 else ''} · "
                  f"{len(its)} open item{'s' if len(its) != 1 else ''}")
        a.caption(f"TC {d['tc'] or '—'} · {d['title_company'] or 'title company not set'} · {counts}"
                  + (f" · {overdue} overdue" if overdue else "") + (" · closed" if d["status"] != "open" else ""))
        b.page_link("views/deal.py", label="Open", icon=":material/arrow_forward:", query_params={"id": str(d["id"])})
