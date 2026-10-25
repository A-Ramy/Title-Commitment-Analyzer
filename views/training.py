"""Training: upload a commitment the team already worked, give the closer's list, and compare. Every item the agent
missed becomes a suggested lesson in the Feedback Inbox; once an admin approves it, it applies to every deal."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from titleagent import pipeline, prompts, training
from titleagent.config import DEAL_TYPES, demo_mode
from titleagent.llm import AgentError, Usage
from titleagent.models import PRIORITY_LABEL
from titleagent.pdf import is_pdf
from ui import html as h
from ui.state import get_llm, get_store, who

store = get_store()
st.title("Train The Agent")
h.status("Upload a commitment your team already worked, paste the list your closer made, and compare. Every gap "
         "becomes a lesson the agent uses on every future deal, once an admin approves it.")

h.heading("The Document", "1")
c1, c2 = st.columns([2, 1])
upload = c1.file_uploader("Worked commitment (PDF)", type=["pdf"], key="train_pdf")
deal_type = c2.selectbox("Deal type", DEAL_TYPES, key="train_type")
name = c2.text_input("Name for this example", placeholder="e.g. Ohio, prior-owner judgments")

h.heading("The Closer's List", "2", "Paste it from the email as is (one item per numbered paragraph), or type it.")
pasted = st.text_area("Closer's list", height=180, label_visibility="collapsed",
                      placeholder="7. Payment and Release of Prior Owner Judgment ...\n8. Payment and Release of ...")
expert = training.parse_expert_list(pasted) if pasted.strip() else []
if expert:
    edited = st.data_editor(pd.DataFrame({"Item": expert}), num_rows="dynamic", width="stretch", key="train_list")
    expert = [str(x).strip() for x in edited["Item"].tolist() if str(x).strip() and str(x) != "nan"]
st.caption("A clean title? Leave the list empty: the agent should then find no Closing Blockers.")

ready = upload is not None or demo_mode()
if st.button("Compare With Agent", type="primary", disabled=not ready,
             help="Runs a full review of the document (about 1–3 minutes) and matches it to the closer's list."):
    from titleagent import demo

    data = upload.getvalue() if upload else demo.sample_commitment_pdf()
    if not is_pdf(data):
        st.error("Upload the commitment as a PDF.")
        st.stop()
    documents = pipeline.Documents(data)
    lessons = store.active_lessons()
    usage = Usage()
    llm = get_llm()
    with st.status("Reviewing the document and comparing…", expanded=True) as s:
        try:
            structure, gaps = pipeline.read_documents(llm, documents, lessons, usage)
            st.write("Read the commitment.")
            analysis = pipeline.review(llm, documents, structure, pipeline.DealInfo(deal_type=deal_type), lessons,
                                       usage, gaps)
            st.write(f"The agent listed {len(analysis.items)} items.")
            blockers = [i for i in analysis.items if i.priority == "blocker"]
            if expert:
                result = training.compare(llm, documents, prompts.system_prompt(lessons), expert, analysis.items,
                                          usage)
            else:  # clean title: everything the agent marked a blocker is an extra
                result = training.Comparison(matched=[], missed=[], extra=blockers)
        except AgentError as exc:
            s.update(label="The comparison did not finish", state="error")
            st.error(str(exc))
            st.stop()
        s.update(label=f"Done · AI cost ${usage.cost:.2f}", state="complete", expanded=False)

    doc_id = store.save_document(data, upload.name if upload else "Sample_Commitment.pdf", "training", by=who())
    example_id = store.add_example(name or (upload.name if upload else "Sample"), doc_id, expert, deal_type,
                                   by=who())
    store.add_score(example_id, result.recall, len(result.matched), len(result.matched) + len(result.missed),
                    len(lessons))
    for item, lesson in result.missed:
        store.add_feedback("training", item, by=who(), detail={"suggested_lesson": lesson, "example_id": example_id})
    st.session_state["train_result"] = (result, expert, len(blockers))

if "train_result" in st.session_state:
    result, expert_seen, n_blockers = st.session_state["train_result"]
    total = len(result.matched) + len(result.missed)
    h.heading("How The Agent Did", "3",
              f"Found {len(result.matched)} of {total} of the closer's items ({result.recall:.0%})." if total else
              f"Clean title check: the agent marked {n_blockers} Closing Blocker(s) (expected 0).")
    a, b, c = st.columns(3)
    with a:
        st.markdown(f"**Both found ({len(result.matched)})**")
        for e, item in result.matched:
            st.html(f'<div class="box good"><b>{h.esc(e[:140])}</b><br><span class="muted">Agent: '
                    f'{h.esc(item.title)} · {h.esc(PRIORITY_LABEL[item.priority])}</span></div>')
    with b:
        st.markdown(f"**Agent missed ({len(result.missed)})**")
        for e, lesson in result.missed:
            st.html(f'<div class="box bad"><b>{h.esc(e[:160])}</b>'
                    f'{f"<div class=lesson><b>Suggested lesson:</b> {h.esc(lesson)}</div>" if lesson else ""}</div>')
        if result.missed:
            st.caption("Each one is waiting in Knowledge → Feedback Inbox for an admin to approve.")
    with c:
        st.markdown(f"**Agent extra ({len(result.extra)})**")
        for item in result.extra:
            st.html(f'<div class="box info"><b>{h.esc(item.title)}</b><br><span class="muted">'
                    f'{h.esc(PRIORITY_LABEL[item.priority])} · {h.esc(", ".join(s.ref for s in item.sources))}'
                    '</span></div>')
        if result.extra:
            st.caption("Extras are often good catches (things closers handle without writing down). If one is "
                       "wrong, add a lesson in Knowledge.")
