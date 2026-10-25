from datetime import date

from titleagent import demo, pipeline
from titleagent.llm import ScriptedLLM, Usage
from titleagent.models import ActionsOut


def run(llm=None, previous=None, updated=False):
    llm = llm or demo.scripted_llm()
    usage = Usage()
    docs = pipeline.Documents(demo.sample_commitment_pdf())
    structure, gaps = pipeline.read_documents(llm, docs, ["lesson one"], usage)
    deal = pipeline.DealInfo(deal_type="Double Close", closing_date=date(2026, 11, 13))
    return pipeline.review(llm, docs, structure, deal, ["lesson one"], usage, gaps, previous=previous,
                           updated_commitment=updated), llm


def test_full_review_on_sample_deal():
    analysis, llm = run()
    cov = analysis.coverage
    assert cov.complete and cov.percent == 100
    assert (cov.requirements_total, cov.exceptions_total) == (9, 8)
    assert [c["step"] for c in llm.calls] == ["structure", "actions", "review"]
    # the second review's find is on the list
    assert any(i.origin == "checklist" and "B-C leg" in i.title for i in analysis.items)
    # blockers first, every commitment quote verified on its page, due dates from the closing date
    assert analysis.items[0].priority == "blocker"
    quoted = [s for i in analysis.items for s in i.sources if s.quote]
    assert quoted and all(s.verified for s in quoted)
    payoff = next(i for i in analysis.items if i.title.startswith("Open mortgage"))
    assert payoff.due_date == "2026-11-03" and payoff.owner == "TC"
    assert len({i.key for i in analysis.items}) == len(analysis.items)


def test_lessons_and_checklist_are_in_the_system_prompt():
    _, llm = run()
    system = llm.calls[0]["system"]
    assert "lesson one" in system and "Subject-to: existing loan" in system
    assert len({c["system"] for c in llm.calls}) == 1  # identical on every call, so it stays cached


def test_numbering_gap_is_sent_back_once():
    full = demo.structure()
    short = full.model_copy(update={"requirements": full.requirements[:7]})  # agent stopped at 7 of 9

    def structure(n, task):
        return short if n == 1 else full

    answers = {"structure": structure, "actions": demo.actions(), "review": demo.second_review()}
    analysis, llm = run(ScriptedLLM(answers))
    retry = [c for c in llm.calls if c["step"] == "structure"]
    assert len(retry) == 2 and "B-I item(s) 8, 9" in retry[1]["task"]
    assert analysis.coverage.complete


def test_undisposed_numbers_are_sent_back_and_then_reported():
    partial = demo.actions()
    partial = ActionsOut(items=partial.items, dispositions=partial.dispositions[:-2],
                         checklist_findings=partial.checklist_findings)
    answers = {"structure": demo.structure(), "actions": partial, "review": demo.second_review()}
    analysis, llm = run(ScriptedLLM(answers))
    assert len([c for c in llm.calls if c["step"] == "actions"]) == 2
    assert analysis.coverage.unaddressed == ["B-II 7", "B-II 8"]
    assert not analysis.coverage.complete


def test_rerun_keeps_status_and_notes():
    first, _ = run()
    worked = [i.model_copy(update={"status": "Ordered", "notes": "payoff requested"}) if i.title.startswith(
        "Open mortgage") else i for i in first.items]
    second, _ = run(previous=worked)
    mortgage = next(i for i in second.items if i.title.startswith("Open mortgage"))
    assert (mortgage.status, mortgage.notes) == ("Ordered", "payoff requested")
    assert not any(i.change for i in second.items)


def test_canonical_refs():
    assert pipeline._canon("B-I #7") == "B-I 7"
    assert pipeline._canon("Schedule B-II item 14.") == "B-II 14"
    assert pipeline._canon("BI 3") == "B-I 3"
