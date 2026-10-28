"""The daily summary: every user gets one email each morning covering all open deals: open Closing Blockers and
items due in the next 3 days (owner, 2026-10-25). Sent through Resend from the company domain."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

import requests

from titleagent.models import DONE_STATUSES, ActionItem

RESEND_URL = "https://api.resend.com/emails"
LAST_RUN = "email_last_run"  # settings key the daily script writes, Settings reads
EASTERN = ZoneInfo("America/New_York")
SOON_DAYS = 3


def _open(items: list[ActionItem]) -> list[ActionItem]:
    return [i for i in items if i.status not in DONE_STATUSES and i.change != "removed"]


def summary_html(deals: list[dict], items_by_deal: dict[int, list[ActionItem]], today: date,
                 app_url: str = "") -> tuple[str, str]:
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
        link = f' <a href="{escape(app_url)}/deal?id={d["id"]}">Open</a>' if app_url else ""
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


def send(api_key: str, sender: str, recipients: list[str], subject: str, html: str) -> None:
    if not recipients:
        raise ValueError("No recipients set (Settings → Daily email).")
    r = requests.post(RESEND_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=30,
                      json={"from": f"Title Agent <{sender}>", "to": recipients, "subject": subject, "html": html})
    if r.status_code >= 300:
        raise RuntimeError(f"Email service returned {r.status_code}: {r.text[:200]}")


def run_record(result: str, detail: str, now: datetime) -> dict:
    """What the daily script stores after each run. result: sent | skipped | failed."""
    return {"at": now.isoformat(), "result": result, "detail": detail}


def run_status(last: dict | None) -> tuple[str, str, str]:
    """(value, sub, tile class) for the Settings tile. The Resend key lives in GitHub, not in the app, so the last
    run the script recorded is the only honest status."""
    if not last:
        return "No Run Yet", "sent from GitHub each weekday morning", "muted"
    at = datetime.fromisoformat(last["at"]).astimezone(EASTERN)
    when = f"{at:%b %d}, {at:%I:%M %p}".replace(", 0", ", ") + " ET"
    if last["result"] == "sent":
        return "Sending", f"last sent {when} · {escape(last['detail'])}", "up"
    if last["result"] == "failed":
        return "Failed", f"{when} · {escape(last['detail'])}", "down"
    return "Skipped", f"{when} · {escape(last['detail'])}", "muted"
