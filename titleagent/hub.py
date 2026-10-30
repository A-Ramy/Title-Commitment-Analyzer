"""The Universal Team Hub connection (hub.totalchb.com, RemyTCHB/HUB → api/title-agent).

Only Closing Blockers go to the hub: one task per deal, "Title - <address>", in Monz's list, marked as added by
"Title Commitment Agent". Each blocker is a subtask (title = the item, a note with the action and the source, the
item's due date). The hub keeps the task in step with what is sent and answers with any blocker ticked or unticked
there; a blocker cleared here shows as done there. Both directions are signed with HUB_SYNC_SECRET
(HMAC-SHA256 of "<unix seconds>.<body>", 5 minutes' leeway).

Sent after every review, re-run, item change and missing item (in the background), and for every open deal each
weekday morning after the 8:00 email (titleagent/daily.py), so a missed message is caught up. Logs say counts,
never deal details (the repository and its Actions logs are public).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import UTC, datetime

import requests

from titleagent.models import STATUSES

log = logging.getLogger("hub")
APP_URL = "https://title.totalchb.com"
HUB = "Universal Team Hub"


def signature(secret: str, body: bytes, ts: int) -> str:
    return "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


def signed_headers(secret: str, body: bytes, ts: int | None = None) -> dict:
    ts = int(time.time()) if ts is None else ts
    return {"Content-Type": "application/json", "X-Hub-Timestamp": str(ts),
            "X-Hub-Signature": signature(secret, body, ts)}


def verify(secret: str | None, body: bytes, ts: str | None, sig: str | None, now: float | None = None) -> bool:
    if not (secret and ts and sig):
        return False
    try:
        t = int(ts)
    except ValueError:
        return False
    if abs((time.time() if now is None else now) - t) > 300:
        return False
    return hmac.compare_digest(signature(secret, body, t), sig)


def payload(store, deal_id: int, app_url: str = APP_URL) -> dict | None:
    """What the hub gets for a deal: its address, a link back, and its Closing Blockers (nothing else)."""
    deal = store.get_deal(deal_id)
    if not deal:
        return None
    blockers = [{"key": i.key, "priority": i.priority, "title": i.title, "action": i.action,
                 "sources": [s.ref for s in i.sources], "due_date": i.due_date, "status": i.status}
                for i in store.get_items(deal_id) if i.priority == "blocker" and i.change != "removed"]
    return {"deal": {"id": deal_id, "address": deal.get("address") or "", "url": f"{app_url}/#/deal/{deal_id}"},
            "blockers": blockers}


def apply_updates(store, deal_id: int, updates: list[dict]) -> int:
    """Blockers ticked or unticked in the hub: Cleared / Open here. Returns how many changed."""
    items = {i.key: i for i in store.get_items(deal_id)}
    applied = 0
    for u in updates or []:
        item, status = items.get(str(u.get("key") or "")), u.get("status")
        if not item or item.priority != "blocker" or status not in STATUSES or item.status == status:
            continue
        who = str(u.get("by") or "").strip()[:80]
        store.update_item(deal_id, item.key, by=f"{HUB} · {who}" if who else HUB, status=status)
        applied += 1
    return applied


def sync(store, secrets, deal_id: int, app_url: str = APP_URL, post=None) -> dict:
    """Send one deal to the hub and copy back what changed there. Raises on failure."""
    body = json.dumps(payload(store, deal_id, app_url) or {}).encode()
    if body == b"{}":
        return {"skipped": "no deal"}
    r = (post or requests.post)(secrets.hub_url, data=body, headers=signed_headers(secrets.hub_secret, body),
                                timeout=30)
    r.raise_for_status()
    out = r.json()
    applied = apply_updates(store, deal_id, out.get("updates") or [])
    _mark(store, deal_id, {"hub_task": out.get("task"), "hub_synced_at": datetime.now(UTC),
                           "hub_error": ""})
    return {"task": out.get("task"), "created": bool(out.get("created")), "changed": bool(out.get("changed")),
            "applied": applied}


def safe_sync(store, secrets, deal_id: int, app_url: str = APP_URL) -> dict | None:
    """sync() for background use: never raises; failures are kept on the deal and retried by the next change
    or the morning catch-up."""
    if not getattr(secrets, "has_hub", False):
        return None
    try:
        return sync(store, secrets, deal_id, app_url)
    except Exception as exc:  # the next run catches it up
        log.warning("hub sync failed for a deal: %s", type(exc).__name__)
        _mark(store, deal_id, {"hub_error": type(exc).__name__})
        return None


def _mark(store, deal_id: int, fields: dict) -> None:
    """Keep the hub status on the deal without moving it up the Deals list (updated_at is left alone)."""
    db = getattr(store, "db", None)
    if db is not None:
        try:
            db.document(f"deals/{deal_id}").update(fields)
        except Exception:
            pass


PHOTO_HOSTS = ("https://firebasestorage.googleapis.com/",)  # where the hub keeps its photos


def team_from_hub(secrets, post=None) -> list[dict]:
    """The hub's Managers and TC department for the Team tab (POST <hub>/team, signed like a sync). The names and
    emails come from the hub's own directory, so they never sit in this repository. Raises on failure."""
    body = b"{}"
    r = (post or requests.post)(secrets.hub_url.rstrip("/") + "/team", data=body,
                                headers=signed_headers(secrets.hub_secret, body), timeout=30)
    r.raise_for_status()
    out = []
    for p in (r.json() or {}).get("people") or []:
        email = str(p.get("email") or "").strip().lower()
        role = p.get("role") if p.get("role") in ("manager", "lead", "member") else "member"
        dept = "TC" if str(p.get("dept") or "").upper() == "TC" else ""
        if not email or not (role == "manager" or dept == "TC"):
            continue
        photo = str(p.get("photo") or "")
        out.append({"name": " ".join(str(p.get("name") or email).split())[:80], "email": email, "role": role,
                    "dept": "" if role == "manager" else dept,
                    "photo": photo if photo.startswith(PHOTO_HOSTS) and len(photo) < 2000 else ""})
    return out
