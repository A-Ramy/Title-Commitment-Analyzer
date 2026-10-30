"""The Universal Team Hub connection (titleagent/hub.py): only Closing Blockers go, signed; changes made in the hub
come back as statuses; the engine takes signed hub updates and sends deals after changes. Made-up data only."""

import json

import pytest

from titleagent import hub
from titleagent.config import Secrets
from titleagent.models import ActionItem, Source

SECRETS = Secrets(None, None, None, hub_url="https://hub.example/api/title-agent", hub_secret="s3cret")


def item(key, priority="blocker", status="Open", **x):
    return ActionItem(key=key, priority=priority, category="Other", title=f"Item {key}", action=f"Do {key}",
                      provided_by="Seller", sources=[Source(ref=f"B-I {key}")], status=status, **x)


def a_deal(store):
    deal_id = store.create_deal(by="pat.tc@totalchb.com", address="1 Sample Way, Exampleton, OH")
    store.replace_items(deal_id, [item("1", due_date="2026-11-05"), item("2", priority="before"),
                                  item("3", priority="fyi"), item("4", status="Cleared"),
                                  item("5", change="removed")])
    return deal_id


class FakeHub:
    def __init__(self, updates=None):
        self.sent, self.updates = [], updates or []

    def __call__(self, url, data, headers, timeout):
        assert hub.verify("s3cret", data, headers["X-Hub-Timestamp"], headers["X-Hub-Signature"])
        self.sent.append(json.loads(data))
        updates = self.updates

        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"ok": True, "task": "ta-x", "created": True, "changed": True, "updates": updates}

        return R()


def test_signatures():
    body = b'{"a":1}'
    head = hub.signed_headers("s3cret", body, ts=1000)
    assert hub.verify("s3cret", body, head["X-Hub-Timestamp"], head["X-Hub-Signature"], now=1100)
    assert not hub.verify("s3cret", body + b" ", head["X-Hub-Timestamp"], head["X-Hub-Signature"], now=1100)
    assert not hub.verify("other", body, head["X-Hub-Timestamp"], head["X-Hub-Signature"], now=1100)
    assert not hub.verify("s3cret", body, head["X-Hub-Timestamp"], head["X-Hub-Signature"], now=2000)
    assert not hub.verify(None, body, head["X-Hub-Timestamp"], head["X-Hub-Signature"], now=1100)


def test_only_closing_blockers_go_and_hub_changes_come_back(store):
    deal_id = a_deal(store)
    fake = FakeHub(updates=[{"key": "1", "status": "Cleared", "by": "Monz Miller"},
                            {"key": "2", "status": "Cleared", "by": "Monz Miller"}])   # not a blocker: ignored
    out = hub.sync(store, SECRETS, deal_id, post=fake)
    sent = fake.sent[0]
    assert sent["deal"] == {"id": deal_id, "address": "1 Sample Way, Exampleton, OH",
                            "url": f"https://title.totalchb.com/#/deal/{deal_id}"}
    assert [b["key"] for b in sent["blockers"]] == ["1", "4"]                 # no Before Closing / FYI / removed
    assert sent["blockers"][0] == {"key": "1", "priority": "blocker", "title": "Item 1", "action": "Do 1",
                                   "sources": ["B-I 1"], "due_date": "2026-11-05", "status": "Open"}
    assert out["applied"] == 1
    items = {i.key: i for i in store.get_items(deal_id)}
    assert items["1"].status == "Cleared" and items["2"].status == "Open"
    assert store.get_deal(deal_id)["hub_task"] == "ta-x"


def test_safe_sync_never_raises(store, monkeypatch):
    deal_id = a_deal(store)

    def down(*a, **k):
        raise ConnectionError("hub down")

    monkeypatch.setattr(hub.requests, "post", down)
    assert hub.safe_sync(store, SECRETS, deal_id) is None
    assert store.get_deal(deal_id)["hub_error"] == "ConnectionError"
    assert hub.safe_sync(store, Secrets(None, None, None), deal_id) is None   # hub not set up: nothing happens


def test_engine_takes_signed_hub_updates_and_sends_changes(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from engine.main import Engine, create_app
    from tests.conftest import firestore_store
    from titleagent import demo

    store = firestore_store()
    fake = FakeHub()
    monkeypatch.setattr(hub.requests, "post", fake)
    tokens = {"tc": {"email": "pat.tc@totalchb.com", "email_verified": True, "uid": "u-tc"}}
    client = TestClient(create_app(Engine(secrets=SECRETS, store=store, llm=demo.scripted_llm,
                                          verify=lambda t: tokens[t])))
    deal_id = a_deal(store)

    body = json.dumps({"deal_id": deal_id, "updates": [{"key": "1", "status": "Cleared", "by": "Monz Miller"}]})
    assert client.post("/v1/hub/items", content=body).status_code == 401                       # unsigned
    bad = hub.signed_headers("wrong", body.encode())
    assert client.post("/v1/hub/items", content=body, headers=bad).status_code == 401
    r = client.post("/v1/hub/items", content=body, headers=hub.signed_headers("s3cret", body.encode()))
    assert r.json() == {"ok": True, "applied": 1}
    assert {i.key: i.status for i in store.get_items(deal_id)}["1"] == "Cleared"
    assert fake.sent == []                                                       # no echo back to the hub

    # a TC reopens a blocker here: the deal goes to the hub; a Before Closing item doesn't trigger it
    client.patch(f"/v1/deals/{deal_id}/items", json={"key": "2", "status": "Cleared"},
                 headers={"Authorization": "Bearer tc"})
    assert fake.sent == []
    client.patch(f"/v1/deals/{deal_id}/items", json={"key": "1", "status": "Open"},
                 headers={"Authorization": "Bearer tc"})
    assert len(fake.sent) == 1 and fake.sent[0]["blockers"][0]["status"] == "Open"


def test_team_from_hub_keeps_managers_and_tc_only():
    sent = {}

    def post(url, data, headers, timeout):
        sent["url"] = url
        assert hub.verify("s3cret", data, headers["X-Hub-Timestamp"], headers["X-Hub-Signature"])

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"people": [
                    {"name": "Pat  Manager", "email": "Pat@totalchb.com", "role": "manager", "dept": "OPS",
                     "photo": "https://firebasestorage.googleapis.com/v0/b/x/o/a.jpg?alt=media&token=t"},
                    {"name": "Lee Lead", "email": "lee@totalchb.com", "role": "lead", "dept": "tc"},
                    {"name": "Sam Member", "email": "sam@totalchb.com", "role": "member", "dept": "TC",
                     "photo": "https://elsewhere.example/p.jpg"},
                    {"name": "Ops Person", "email": "ops@totalchb.com", "role": "member", "dept": "OPS"}]}
        return R()

    people = hub.team_from_hub(SECRETS, post=post)
    assert sent["url"] == "https://hub.example/api/title-agent/team"
    assert [p["email"] for p in people] == ["pat@totalchb.com", "lee@totalchb.com", "sam@totalchb.com"]
    assert people[0]["name"] == "Pat Manager" and people[0]["dept"] == "" and people[0]["photo"].startswith("https://")
    assert people[1]["dept"] == "TC" and people[2]["photo"] == ""  # only the hub's own photo store
