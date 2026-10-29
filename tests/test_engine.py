"""The v2 engine end to end: sign-in rules, upload → read → confirm → review, re-run, exports, list edits, report
missing, training, admin actions. Firestore via the emulator; scripted AI answers; made-up sample data."""

import pytest

from titleagent import demo
from titleagent.config import Secrets

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from engine.main import Engine, create_app  # noqa: E402

TOKENS = {
    "tc": {"email": "pat.tc@totalchb.com", "email_verified": True, "uid": "u-tc"},
    "owner": {"email": "owner@totalchb.com", "email_verified": True, "uid": "u-owner"},
    "outsider": {"email": "someone@gmail.com", "email_verified": True, "uid": "u-x"},
    "unverified": {"email": "new@totalchb.com", "email_verified": False, "uid": "u-new"},
}


def verify(token: str) -> dict:
    if token not in TOKENS:
        raise ValueError("bad token")
    return TOKENS[token]


@pytest.fixture
def setup():
    from tests.conftest import firestore_store

    store = firestore_store()
    client = TestClient(create_app(Engine(secrets=Secrets(None, None, None, None), store=store,
                                          llm=demo.scripted_llm, verify=verify)))
    return client, store


def h(who: str) -> dict:
    return {"Authorization": f"Bearer {who}"}


def test_only_verified_company_accounts_get_in(setup):
    client, _ = setup
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/me", headers=h("forged")).status_code == 401
    assert client.get("/v1/me", headers=h("outsider")).status_code == 403
    assert client.get("/v1/me", headers=h("unverified")).status_code == 403
    assert client.get("/v1/me", headers=h("tc")).json() == {"email": "pat.tc@totalchb.com", "admin": True}


def test_a_full_deal_through_the_engine(setup):
    client, store = setup
    store.blobs.put("uploads/u-tc/a.pdf", demo.sample_commitment_pdf(), "application/pdf")
    # someone else's upload can't be read
    theirs = {"job_id": "job-read-0001", "commitment_path": "uploads/u-tc/a.pdf"}
    assert client.post("/v1/read", headers=h("owner"), json=theirs).status_code == 400

    r = client.post("/v1/read", headers=h("tc"), json={"job_id": "job-read-0002",
                                                        "commitment_path": "uploads/u-tc/a.pdf",
                                                        "commitment_name": "Sample.pdf"})
    assert r.status_code == 200, r.text
    read = r.json()
    assert read["summary"]["requirements"] > 0 and not read["summary"]["missing"]
    assert read["prefill"]["address"]
    assert store.db.document("jobs/job-read-0002").get().get("status") == "done"
    with pytest.raises(KeyError):
        store.blobs.get("uploads/u-tc/a.pdf")  # the upload is cleaned up once saved as the deal's document

    fields = {**read["prefill"], "deal_type": "Double Close", "closing_date": "2026-11-13", "tc": "Pat"}
    r = client.post("/v1/review", headers=h("tc"), json={"job_id": "job-review-01", "draft_id": read["draft_id"],
                                                          "fields": fields})
    assert r.status_code == 200, r.text
    deal_id = r.json()["deal_id"]
    deal = store.get_deal(deal_id)
    assert deal["tc"] == "Pat" and deal["closing_date"].isoformat() == "2026-11-13"
    items = store.get_items(deal_id)
    assert items and all(i.due_date for i in items if i.due_rule != "none")
    assert store.get_draft(read["draft_id"]) is None

    # the TC works the list
    key = items[0].key
    assert client.patch(f"/v1/deals/{deal_id}/items", headers=h("tc"),
                        json={"key": key, "status": "Ordered", "notes": "payoff requested"}).status_code == 200
    assert client.patch(f"/v1/deals/{deal_id}/items", headers=h("tc"),
                        json={"key": key, "status": "Done-ish"}).status_code == 400
    assert client.patch(f"/v1/deals/{deal_id}/items", headers=h("tc"),
                        json={"key": "nope", "status": "Open"}).status_code == 404
    assert store.get_items(deal_id)[0].status == "Ordered"

    # re-run keeps statuses and notes
    assert client.post(f"/v1/deals/{deal_id}/rerun", headers=h("tc"), json={"job_id": "job-rerun-01"}).status_code \
        == 200
    again = {i.key: i for i in store.get_items(deal_id)}
    assert again[key].status == "Ordered" and again[key].notes == "payoff requested"

    # exports, including Closing Blockers only
    r = client.get(f"/v1/deals/{deal_id}/export?format=pdf&include=blockers", headers=h("tc"))
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert "Closing_Blockers.pdf" in r.headers["content-disposition"]
    assert client.get(f"/v1/deals/{deal_id}/export?format=exe", headers=h("tc")).status_code == 400
    assert client.get(f"/v1/deals/{deal_id}/export?format=csv", headers=h("outsider")).status_code == 403

    # report missing goes on the list and into the inbox
    r = client.post(f"/v1/deals/{deal_id}/missing", headers=h("tc"),
                    json={"what": "Final water bill", "why": "City lien."})
    assert r.status_code == 200
    assert store.get_items(deal_id)[-1].title == "Final water bill"
    assert [f["text"] for f in store.list_feedback()] == ["Final water bill"]

    # closing the deal
    assert client.patch(f"/v1/deals/{deal_id}", headers=h("tc"), json={"status": "closed"}).status_code == 200
    assert store.get_deal(deal_id)["status"] == "closed"


def test_admin_actions(setup):
    client, store = setup
    assert client.put("/v1/settings", headers=h("owner"), json={"admins": ["owner@totalchb.com"]}).status_code == 200
    assert client.get("/v1/me", headers=h("tc")).json()["admin"] is False
    assert client.post("/v1/lessons", headers=h("tc"), json={"text": "A rule."}).status_code == 403
    assert client.put("/v1/settings", headers=h("tc"), json={"tcs": ["Pat"]}).status_code == 403
    assert client.put("/v1/settings", headers=h("owner"), json={"bogus": 1}).status_code == 400
    assert client.put("/v1/settings", headers=h("owner"),
                      json={"google_folder_id": "https://drive.google.com/drive/folders/1AbC?usp=sharing",
                            "due_offsets": {"payoff": "12", "junk": 3}}).status_code == 200
    s = store.get_settings()
    assert s["google_folder_id"] == "1AbC" and s["due_offsets"] == {"payoff": 12}

    fid = store.add_feedback("missing", "Water bill", by="pat.tc@totalchb.com")
    assert client.post(f"/v1/feedback/{fid}/resolve", headers=h("owner"),
                       json={"approve": True, "lesson": ""}).status_code == 400
    r = client.post(f"/v1/feedback/{fid}/resolve", headers=h("owner"),
                    json={"approve": True, "lesson": "Check final water bills on every deal."})
    lesson_id = r.json()["lesson_id"]
    assert "Check final water bills on every deal." in store.active_lessons()
    client.patch(f"/v1/lessons/{lesson_id}", headers=h("owner"), json={"active": False})
    assert "Check final water bills on every deal." not in store.active_lessons()


def test_training_through_the_engine(setup):
    client, store = setup
    store.blobs.put("uploads/u-tc/t.pdf", demo.sample_commitment_pdf(), "application/pdf")
    r = client.post("/v1/training", headers=h("tc"), json={"job_id": "job-train-01", "path": "uploads/u-tc/t.pdf",
                                                            "deal_type": "Wholesale (Assignment)", "name": "Sample",
                                                            "expert": []})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["blockers"] == len(out["extra"]) and store.list_examples()[0]["name"] == "Sample"
