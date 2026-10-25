import csv
import io
from datetime import date

from openpyxl import load_workbook

from titleagent import demo, pipeline
from titleagent.exports import Checklist, document, tabular
from titleagent.llm import Usage
from titleagent.prompts import SEED_LESSONS
from titleagent.storage import Store


def analysis():
    llm, usage = demo.scripted_llm(), Usage()
    docs = pipeline.Documents(demo.sample_commitment_pdf())
    structure, gaps = pipeline.read_documents(llm, docs, [], usage)
    return pipeline.review(llm, docs, structure, pipeline.DealInfo(closing_date=date(2026, 11, 13)), [], usage, gaps)


def test_store_round_trip(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 't.db'}")
    assert store.active_lessons() == SEED_LESSONS
    doc = store.save_document(b"%PDF-1.4 x", "c.pdf", "commitment", by="tc@x")
    deal = store.create_deal(by="tc@x", address="1427 Maple Ave", deal_type="Double Close",
                             closing_date=date(2026, 11, 13))
    store.attach_document(doc, deal)
    a = analysis()
    store.save_run(deal, a, doc, None, False, by="tc@x")
    items = store.get_items(deal)
    assert [i.key for i in items] == [i.key for i in a.items]
    store.update_item(deal, items[0].key, by="tc@x", status="Cleared", notes="done")
    assert store.get_items(deal)[0].status == "Cleared"
    assert deal in store.open_items_by_deal()
    fb = store.add_feedback("missing", "Water bill", by="tc@x", deal_id=deal)
    lesson = store.resolve_feedback(fb, True, "Always check final water bills.", by="admin@x")
    assert lesson and store.active_lessons()[-1] == "Always check final water bills."
    assert store.list_feedback("pending") == []
    store.set_setting("tcs", ["Pat"])
    assert store.get_settings()["tcs"] == ["Pat"]


def test_every_export_format():
    a = analysis()
    cl = Checklist(title="1427 Maple Ave, Columbus, OH", meta=[("Deal type", "Double Close")], items=a.items,
                   coverage_line="B-I 9/9")
    rows = list(csv.reader(io.StringIO(tabular.to_csv(cl, include_fyi=False).decode("utf-8-sig"))))
    header = rows.index(next(r for r in rows if r and r[0] == "#"))
    body = rows[header + 1:]
    assert len(body) == len([i for i in a.items if i.priority != "fyi"])
    assert body[0][1] == "Closing Blocker"
    wb = load_workbook(io.BytesIO(tabular.to_xlsx(cl)))
    assert wb.active.max_row > len(a.items)
    assert document.to_pdf(cl).startswith(b"%PDF")
    assert document.to_docx(cl)[:2] == b"PK"
    assert cl.filename("pdf") == "1427_Maple_Ave_Columbus_OH_Title_Checklist.pdf"
