"""Shared page pieces: branded sidebar, the tab capsule, the setup screen."""

from __future__ import annotations

import streamlit as st

from titleagent.config import demo_mode
from titleagent.models import DONE_STATUSES
from ui import html as h
from ui.auth import sign_out_button
from ui.brand import logo, theme_toggle
from ui.state import get_store, who


def sidebar(tools: list, deal_page) -> None:
    store = get_store()
    with st.sidebar:
        st.image(logo(), width="stretch")
        st.html('<div class="brand-sub">Title Agent</div>')
        theme_toggle()
        if demo_mode():
            st.warning("Sample data (developer preview)")
        deals = store.list_deals(status="open")[:6]
        if deals:
            st.html('<div class="side-h">Open Deals</div>')
            items = store.open_items_by_deal()
            for d in deals:
                open_blockers = sum(1 for i in items.get(d["id"], []) if i.priority == "blocker"
                                    and i.status not in DONE_STATUSES and i.change != "removed")
                label = d["address"].split(",")[0] or f"Deal {d['id']}"
                st.page_link(deal_page, label=f"{label} · {open_blockers} blocker{'s' if open_blockers != 1 else ''}",
                             query_params={"id": str(d["id"])}, width="stretch")
        st.html('<div class="side-h">Tools</div>')
        pending = len(store.list_feedback("pending"))
        for p in tools:
            label = f"{p.title} ({pending})" if p.url_path == "knowledge" and pending else p.title
            st.page_link(p, label=label, width="stretch")
        st.html(f'<div class="kv" style="margin-top:10px"><span>Signed in as <b>{h.esc(who())}</b></span></div>')
        sign_out_button()


def tab_capsule(pages: list) -> None:
    with st.container(key="tabs", horizontal=True, width="content", gap=None):
        for p in pages:
            st.page_link(p)


def setup_screen() -> None:
    st.title("Connect The AI")
    st.write("The Title Agent reads commitments with Claude. Add the Anthropic API key to the app's secrets:")
    st.markdown(
        """
1. In Streamlit Community Cloud, open the app → **Settings → Secrets**.
2. Add a line: `ANTHROPIC_API_KEY = "sk-ant-..."` (locally: put it in `.env`).
3. Save. The app restarts and this screen goes away.
"""
    )
