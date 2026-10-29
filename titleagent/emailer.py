"""The daily summary: every user gets one email each morning covering all open deals: open Closing Blockers and
items due in the next 3 days (owner, 2026-10-25). Sent through Resend from the company domain."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

import requests

from titleagent.models import DONE_STATUSES, ActionItem

RESEND_URL = "https://api.resend.com/emails"
LAST_RUN = "email_last_run"  # settings key the daily script writes, Settings reads
EASTERN = ZoneInfo("America/New_York")
# 8:00 AM Eastern on weekdays, without fail (owner 2026-10-28). GitHub's scheduler runs hours late or not at all,
# so early-morning runs hand the email to Resend with a delivery time and Resend sends it at 8:00 sharp.
SEND_AT = time(8, 0)
LATEST_TO_SCHEDULE = time(7, 58)  # a run after this sends right away instead
SOON_DAYS = 3


def _open(items: list[ActionItem]) -> list[ActionItem]:
    return [i for i in items if i.status not in DONE_STATUSES and i.change != "removed"]


def summary_html(deals: list[dict], items_by_deal: dict[int, list[ActionItem]], today: date,
                 app_url: str = "", hash_links: bool = False) -> tuple[str, str]:
    """(subject, html)."""
    soon = today + timedelta(days=SOON_DAYS)
    blocks, total_blockers, total_due = [], 0, 0
    for d in deals:
        items = _open(items_by_deal.get(d["id"], []))
        blockers = [i for i in items if i.priority == "blocker"]
        due = [i for i in items if i.due_date and i.due_date <= soon.isoformat()]
        total_blockers += len(blockers)
        total_due += len(due)
        if not (blockers or due):
            continue
        closing = d.get("closing_date")
        lines = "".join(
            f"<li><b>{escape(i.title)}</b> · {escape(i.provided_by)}"
            f"{f' · due {escape(i.due_date)}' if i.due_date else ''}"
            f"{' · <span style=color:#BD2239>OVERDUE</span>' if i.due_date and i.due_date < today.isoformat() else ''}"
            f"</li>" for i in sorted(blockers + [x for x in due if x not in blockers],
                                     key=lambda x: (x.priority != "blocker", x.due_date or "9999")))
        path = f"/#/deal/{d['id']}" if hash_links else f"/deal?id={d['id']}"  # v2 page / Streamlit app
        link = f' <a href="{escape(app_url.rstrip("/") + path)}">Open</a>' if app_url else ""
        blocks.append(f"<h3 style='color:#4D458A;margin:18px 0 4px'>{escape(d['address'] or 'Deal ' + str(d['id']))}"
                      f"</h3><div style='color:#767388;font-size:13px'>{escape(d.get('deal_type') or '')}"
                      f"{f' · closing {closing}' if closing else ''} · TC {escape(d.get('tc') or 'unassigned')}"
                      f"{link}</div><ul>{lines}</ul>")
    subject = (f"Title Agent: {total_blockers} open blocker{'s' if total_blockers != 1 else ''}, "
               f"{total_due} due soon ({today:%b %d})")
    html = (f"<div style='font-family:Arial,sans-serif;max-width:680px'><h2 style='color:#4D458A'>Title Agent daily "
            f"summary · {today:%A, %b %d}</h2>"
            + ("".join(blocks) or "<p>No open blockers and nothing due in the next 3 days.</p>")
            + "<p style='color:#767388;font-size:12px'>Total Cash Home Buyers · Title Agent</p></div>")
    return subject, html


def send(api_key: str, sender: str, recipients: list[str], subject: str, html: str,
         deliver_at: datetime | None = None) -> None:
    """Sends now, or hands the email to Resend to deliver at deliver_at."""
    if not recipients:
        raise ValueError("No recipients set (Settings → Daily email).")
    body = {"from": f"Title Agent <{sender}>", "to": recipients, "subject": subject, "html": html}
    if deliver_at:
        body["scheduled_at"] = deliver_at.isoformat()
    r = requests.post(RESEND_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=30, json=body)
    if r.status_code >= 300:
        raise RuntimeError(f"Email service returned {r.status_code}: {r.text[:200]}")


def plan(now: datetime) -> tuple[str, datetime | None]:
    """What a run at `now` does: ('skip', None) on a weekend in Eastern time; ('schedule', 8:00 AM ET today) when
    it's early enough; else ('now', None): a late run sends straight away."""
    local = now.astimezone(EASTERN)
    if local.weekday() >= 5:
        return "skip", None
    if local.time() < LATEST_TO_SCHEDULE:
        return "schedule", datetime.combine(local.date(), SEND_AT, tzinfo=EASTERN)
    return "now", None


def already_done(last: dict | None, day: date) -> bool:
    """True when an earlier run already sent or scheduled the email for this day (several runs try each morning)."""
    return bool(last) and last.get("for") == day.isoformat() and last.get("result") in ("sent", "scheduled")


def run_record(result: str, detail: str, now: datetime, day: date | None = None,
               deliver_at: datetime | None = None) -> dict:
    """What the daily script stores after each run. result: scheduled | sent | test | skipped | failed."""
    return {"at": now.isoformat(), "result": result, "detail": detail, "for": day.isoformat() if day else None,
            "deliver_at": deliver_at.isoformat() if deliver_at else None}


def _when(at: datetime) -> str:
    at = at.astimezone(EASTERN)
    return f"{at:%b %d}, {at:%I:%M %p}".replace(", 0", ", ") + " ET"


def run_status(last: dict | None, now: datetime | None = None) -> tuple[str, str, str]:
    """(value, sub, tile class) for the Settings tile. The Resend key lives in GitHub, not in the app, so the last
    run the script recorded is the only honest status."""
    if not last:
        return "No Run Yet", "sent from GitHub each weekday at 8:00 AM ET", "muted"
    when = _when(datetime.fromisoformat(last["at"]))
    detail = escape(last["detail"])
    if last["result"] == "scheduled" and last.get("deliver_at"):
        deliver = datetime.fromisoformat(last["deliver_at"])
        if (now or datetime.now(EASTERN)) >= deliver:
            return "Sending", f"last sent {_when(deliver)} · {detail}", "up"
        return "Scheduled", f"goes out {_when(deliver)} · {detail}", "up"
    if last["result"] in ("sent", "test"):
        return "Sending", f"{'test sent' if last['result'] == 'test' else 'last sent'} {when} · {detail}", "up"
    if last["result"] == "failed":
        return "Failed", f"{when} · {detail}", "down"
    return "Skipped", f"{when} · {detail}", "muted"
