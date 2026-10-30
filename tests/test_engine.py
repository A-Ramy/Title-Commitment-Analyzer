"""The v2 engine end to end: sign-in rules, upload → read → confirm → review, re-run, exports, list edits, report
missing, training, admin actions. Firestore via the emulator; scripted AI answers; made-up sample data."""

from urllib.parse import unquote

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
    client = TestClient(create_app(Engine(secrets=Secrets(None, None, None), store=store,
                                          llm=demo.scripted_llm, verify=verify)))
    return client, store


def h(who: str) -> dict:
    return {"Authorization": f"Bearer {who}"}


def test_only_verified_company_accounts_get_in(setup):
    client, _ = setup
    assert client.get("/health").json() == {"ok": True}  # Cloud Run swallows paths ending in "z"
    assert client.get("/docs").status_code == 404
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/me", headers=h("forged")).status_code == 401
    assert client.get("/v1/me", headers=h("outsider")).status_code == 403
    assert client.get("/v1/me", headers=h("unverified")).status_code == 403
    assert client.get("/v1/me", headers=h("tc")).json() == {
        "email": "pat.tc@totalchb.com", "admin": True, "role": "manager",
        "can": {"approve_lessons": True, "report_missing": True}}
    ref = client.get("/v1/reference", headers=h("tc")).json()
    assert "Double Close" in ref["deal_types"] and sum(len(g["checks"]) for g in ref["checklist"]) == 34
    assert ref["connections"]["google"] is None and ref["connections"]["hub"] is False
    assert "function doPost" in ref["google_script"]
    assert ref["settings_defaults"]["due_offsets"]["payoff"] == 10
    assert client.get("/v1/reference").status_code == 401


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
    # a due date with a time (the picker), a bad time, then Remove clears both
    patch = lambda body: client.patch(f"/v1/deals/{deal_id}/items", headers=h("tc"), json={"key": key, **body})  # noqa: E731
    assert patch({"due_date": "2026-11-05", "due_time": "17:30"}).status_code == 200
    got = store.get_items(deal_id)[0]
    assert (got.due_date, got.due_time) == ("2026-11-05", "17:30")
    assert patch({"due_date": "2026-11-05", "due_time": "25:00"}).status_code == 400
    assert patch({"due_date": "", "due_time": ""}).status_code == 200
    got = store.get_items(deal_id)[0]
    assert (got.due_date, got.due_time) == (None, None)
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
    assert "Closing_Blockers_20" in r.headers["content-disposition"] and r.headers["x-drive-copy"] == "off"
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
    assert s["google_folder_id"] == "1AbC"
    assert s["due_offsets"] == {"payoff": 12, "curative": 14, "documents": 5, "bring_down": 5, "closing": 0}

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


def test_morning_run_only_for_the_scheduler_and_sends_once(setup, monkeypatch):
    from datetime import UTC, datetime

    import engine.main as engine_main
    from titleagent import daily

    _, store = setup
    scheduler = "title-agent-scheduler@example.iam.gserviceaccount.com"
    tasks = {"sched": {"email": scheduler, "email_verified": True},
             "other": {"email": "someone@example.iam.gserviceaccount.com", "email_verified": True}}
    client = TestClient(create_app(Engine(secrets=Secrets(None, None, "re_test", tasks_caller=scheduler),
                                          store=store, llm=demo.scripted_llm, verify=verify,
                                          verify_task=lambda t: tasks[t])))
    for headers in ({}, h("other"), h("tc"), h("forged")):
        assert client.post("/v1/tasks/morning", headers=headers).status_code == 401

    class Monday8am(datetime):  # Mon Nov 2 2026, 8:00 AM Eastern (EST)
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 2, 13, 0, tzinfo=UTC)

    monkeypatch.setattr(engine_main, "datetime", Monday8am)
    sent = []
    monkeypatch.setattr(daily, "send", lambda key, sender, to, subject, html, at=None: sent.append((subject, at)))
    store.set_setting("email_recipients", ["pat.tc@totalchb.com"], by="test")
    first = client.post("/v1/tasks/morning", headers=h("sched")).json()
    assert first["email"] == "sent" and len(sent) == 1 and sent[0][1] is None  # sent at once, not scheduled
    assert "Closing Blocker" in sent[0][0]
    assert client.post("/v1/tasks/morning", headers=h("sched")).json()["email"] == "done" and len(sent) == 1
    assert store.get_settings()["email_last_run"]["result"] == "sent"


def test_team_tab_sets_admins_and_tcs(setup):
    client, store = setup
    photo = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
    team = [{"name": "Pat  Tc", "email": "Pat.TC@totalchb.com", "role": "manager", "dept": "TC", "photo": photo},
            {"name": "Sam Member", "email": "sam@totalchb.com", "role": "member", "dept": "TC"},
            {"name": "Lee Leader", "email": "lee@totalchb.com", "role": "lead", "dept": "TC"},
            {"name": "Out Of Tc", "email": "ops@totalchb.com", "role": "member", "dept": ""}]
    assert client.put("/v1/team", json={"people": team}, headers=h("tc")).json() == {"ok": True}
    s = store.get_settings()
    assert s["admins"] == ["pat.tc@totalchb.com"] and s["tcs"] == ["Lee Leader", "Sam Member"]
    assert s["team"][0] == {"name": "Pat Tc", "email": "pat.tc@totalchb.com", "role": "manager", "dept": "",
                            "photo": photo}
    # now only managers change it, nobody can drop their own manager role, and only company sign-ins are allowed
    assert client.put("/v1/team", json={"people": team}, headers=h("owner")).status_code == 403
    demoted = [{**team[0], "role": "member"}, *team[1:]]
    assert client.put("/v1/team", json={"people": demoted}, headers=h("tc")).status_code == 400
    outsider = [*team, {"name": "X", "email": "x@gmail.com", "role": "member"}]
    assert client.put("/v1/team", json={"people": outsider}, headers=h("tc")).status_code == 400
    twice = [*team, {"name": "Again", "email": "sam@totalchb.com", "role": "member"}]
    assert client.put("/v1/team", json={"people": twice}, headers=h("tc")).status_code == 400
    bad_photo = [{**team[0], "photo": "javascript:alert(1)"}, *team[1:]]
    assert client.put("/v1/team", json={"people": bad_photo}, headers=h("tc")).status_code == 400


def test_permissions_for_team_leaders_and_members(setup):
    client, store = setup
    team = [{"name": "Pat Tc", "email": "pat.tc@totalchb.com", "role": "manager"},
            {"name": "Owner Lead", "email": "owner@totalchb.com", "role": "lead", "dept": "TC"}]
    assert client.put("/v1/team", json={"people": team}, headers=h("tc")).status_code == 200
    me = client.get("/v1/me", headers=h("owner")).json()
    assert me["role"] == "lead" and me["can"] == {"approve_lessons": True, "report_missing": True} and not me["admin"]
    assert client.post("/v1/lessons", json={"text": "A general rule."}, headers=h("owner")).status_code == 200
    assert client.put("/v1/settings", json={"email_from": "x@totalchb.com"}, headers=h("owner")).status_code == 403
    off = {"lead": {"approve_lessons": False, "report_missing": False}, "member": {"approve_lessons": False}}
    assert client.put("/v1/settings", json={"permissions": off}, headers=h("tc")).status_code == 200
    assert store.get_settings()["permissions"]["member"] == {"approve_lessons": False, "report_missing": True}
    assert client.get("/v1/me", headers=h("owner")).json()["can"] == {"approve_lessons": False, "report_missing": False}
    assert client.post("/v1/lessons", json={"text": "Another rule."}, headers=h("owner")).status_code == 403
    assert client.post("/v1/deals/1/missing", json={"what": "x"}, headers=h("owner")).status_code == 403


def test_every_export_is_also_saved_in_its_drive_folder(monkeypatch):
    from tests.conftest import firestore_store
    from titleagent.exports import google
    from titleagent.models import ActionItem, Source

    store = firestore_store()
    secrets = Secrets(None, None, None, google_export_url="https://script.google.com/macros/s/x/exec",
                      google_export_key="k1")
    client = TestClient(create_app(Engine(secrets=secrets, store=store, llm=demo.scripted_llm, verify=verify)))
    deal_id = store.create_deal(by="pat.tc@totalchb.com", address="1 Sample Way, Exampleton, OH")
    store.replace_items(deal_id, [ActionItem(key="1", priority="blocker", category="Other", title="Item", action="Do",
                                             provided_by="Seller", sources=[Source(ref="B-I 1")])])
    saved = []

    def export(_secrets, folder, name, data, kind, timeout=90):
        if folder == "broken":
            raise google.GoogleExportError("The export key doesn't match.")
        saved.append((folder, name, kind, data[:4]))
        return "https://drive.google.com/file/d/f1"

    monkeypatch.setattr(google, "export", export)
    r = client.get(f"/v1/deals/{deal_id}/export?format=pdf", headers=h("tc"))  # no folder set yet: just the download
    assert r.status_code == 200 and r.headers["x-drive-copy"] == "off"
    assert "folder" in unquote(r.headers["x-drive-note"])

    store.set_setting("google_folder_id", "1Fold", by="test")
    r = client.get(f"/v1/deals/{deal_id}/export?format=pdf", headers=h("tc"))
    assert r.content.startswith(b"%PDF") and (r.headers["x-drive-copy"], r.headers["x-drive-note"]) == ("saved", "PDF")
    folder, name, kind, head = saved[-1]
    assert (folder, kind, head) == ("1Fold", "pdf", b"%PDF")
    assert name.startswith("1 Sample Way, Exampleton, OH · Title Checklist · 20") and name.endswith(" ET.pdf")

    r = client.post(f"/v1/deals/{deal_id}/google", json={"kind": "sheet", "include": "blockers"}, headers=h("tc"))
    assert r.json() == {"link": "https://drive.google.com/file/d/f1", "folder": "Google Sheets"}
    assert saved[-1][2] == "sheet" and " · Closing Blockers · " in saved[-1][1] and not saved[-1][1].endswith(".xlsx")

    store.set_setting("google_folder_id", "broken", by="test")  # Drive fails: the download still comes
    r = client.get(f"/v1/deals/{deal_id}/export?format=csv", headers=h("tc"))
    assert r.status_code == 200 and r.headers["x-drive-copy"] == "failed"
    assert unquote(r.headers["x-drive-note"]) == "The export key doesn't match."
