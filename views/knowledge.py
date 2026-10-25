"""Knowledge: what the agent knows beyond the commitment itself. The Feedback Inbox (admins approve lessons), the
lessons the agent follows on every deal, and the scorecard from training examples."""

from __future__ import annotations

import streamlit as st

from titleagent import checklist
from ui import html as h
from ui.state import get_store, is_admin, who

store = get_store()
admin = is_admin()
st.title("Knowledge")
h.status("Every lesson came from your team: the first set from the 8 worked commitments, the rest from training and "
         "feedback. The agent follows every active lesson on every deal.")

lessons = store.list_lessons()
active = [x for x in lessons if x["active"]]
inbox = store.list_feedback("pending")
scores = store.list_scores()
latest: dict[int, dict] = {}
for s in scores:
    latest[s["example_id"]] = s
matched = sum(s["matched"] for s in latest.values())
total = sum(s["total"] for s in latest.values())
h.tiles([
    ("Finds Expert Items", f"{matched / total:.0%}" if total else "—",
     f"across {len(latest)} training example(s)" if latest else "run Training to measure", "up" if total else "muted"),
    ("Active Lessons", str(len(active)), f"{len(lessons) - len(active)} turned off"),
    ("Pro Checklist", str(len(checklist.CHECKS)), "checks across " + str(len(checklist.GROUPS)) + " groups"),
    ("Feedback Waiting", str(len(inbox)), "needs an admin" if inbox else "inbox is empty",
     "down" if inbox else "up"),
])

# ---------------------------------------------------------------- inbox
h.heading("Feedback Inbox", "1", "From Report Missing Item, per-item feedback and training gaps")
if not inbox:
    h.box("Inbox is empty. Every piece of feedback has been reviewed.", "good")
KIND = {"missing": "Missing item", "not_needed": "Not needed", "wrong": "Wrong info", "training": "Training gap"}
for f in inbox:
    detail = f["detail"] or {}
    suggested = detail.get("suggested_lesson") or (
        f"On every commitment, check for: {f['text']}. {detail.get('why', '')}".strip() if f["kind"] == "missing" else
        f"Do not list this as an action item when it appears: {f['text']}" if f["kind"] == "not_needed" else
        f["text"])
    with st.container(key=f"card-fb-{f['id']}"):
        st.markdown(f"**{f['text'][:200]}**  \n:orange-badge[{KIND.get(f['kind'], f['kind'])}] "
                    f"{f['created_by']} · {f['created_at']:%b %d, %Y}"
                    + (f" · deal {f['deal_id']}" if f["deal_id"] else "")
                    + (f" · {detail['where']}" if detail.get("where") else ""))
        if detail.get("why"):
            st.caption(detail["why"])
        text = st.text_area("Lesson the agent will follow", value=suggested, key=f"lesson_{f['id']}",
                            disabled=not admin)
        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button("Approve Lesson", key=f"ap_{f['id']}", type="primary", disabled=not admin or not text.strip()):
            store.resolve_feedback(f["id"], True, text, by=who())
            st.rerun()
        if b2.button("Reject", key=f"rj_{f['id']}", disabled=not admin):
            store.resolve_feedback(f["id"], False, by=who())
            st.rerun()
if inbox and not admin:
    st.caption("Only admins approve lessons (Settings → Admins).")

# ---------------------------------------------------------------- lessons
h.heading("Lessons", "2", "Turn a lesson off to stop the agent using it; it takes effect on the next review")
for x in lessons:
    c1, c2 = st.columns([8, 1])
    c1.markdown(f"{x['text']}  \n:gray[{x['source'].title()} · {x['created_by']} · {x['created_at']:%b %d, %Y}"
                f"{' · approved by ' + x['approved_by'] if x['approved_by'] else ''}]")
    on = c2.toggle("Active", value=x["active"], key=f"les_{x['id']}", disabled=not admin, label_visibility="collapsed")
    if on != x["active"]:
        store.set_lesson(x["id"], active=on)
        st.rerun()
if admin:
    with st.form("new_lesson", clear_on_submit=True):
        new = st.text_area("Add a lesson", placeholder="e.g. In Florida, always order a municipal lien search.")
        if st.form_submit_button("Add Lesson") and new.strip():
            store.add_lesson(new, source="manual", by=who())
            st.rerun()

# ---------------------------------------------------------------- examples
h.heading("Training Examples", "3", "Re-run any of them from Training after lessons change")
examples = store.list_examples()
if not examples:
    h.box("No training examples saved yet. Add them on the Training tab.", "info")
for e in examples:
    s = latest.get(e["id"])
    st.markdown(f"**{e['name']}** · {e['deal_type']} · {len(e['expert_items'])} closer item(s)"
                + (f" · agent found {s['matched']}/{s['total']} on {s['run_at']:%b %d}" if s else ""))

# ---------------------------------------------------------------- checklist
with st.expander("The professional checklist the agent runs on every deal"):
    for g in checklist.GROUPS:
        st.markdown(f"**{g}**")
        for c in (c for c in checklist.CHECKS if c.group == g):
            scope = "" if c.deal_types == checklist.ALL else f" _(only {', '.join(c.deal_types)})_"
            st.markdown(f"- **{c.name}**{scope}: {c.look_for}")
