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
# The daily email in the app's design (branded_html), drafted 2026-10-30: it goes out once the owner approves it.
BRANDED = False


def _open(items: list[ActionItem]) -> list[ActionItem]:
    return [i for i in items if i.status not in DONE_STATUSES and i.change != "removed"]


def summary_html(deals: list[dict], items_by_deal: dict[int, list[ActionItem]], today: date,
                 app_url: str = "", branded: bool | None = None) -> tuple[str, str]:
    """(subject, html). The branded design once BRANDED is on; until then the plain email."""
    if BRANDED if branded is None else branded:
        return branded_html(deals, items_by_deal, today, app_url)
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
        link = f' <a href="{escape(app_url.rstrip("/"))}/#/deal/{d["id"]}">Open</a>' if app_url else ""
        blocks.append(f"<h3 style='color:#4D458A;margin:18px 0 4px'>{escape(d['address'] or 'Deal ' + str(d['id']))}"
                      f"</h3><div style='color:#767388;font-size:13px'>{escape(d.get('deal_type') or '')}"
                      f"{f' · closing {closing}' if closing else ''} · TC {escape(d.get('tc') or 'unassigned')}"
                      f"{link}</div><ul>{lines}</ul>")
    subject = (f"Title Commitment Agent: {total_blockers} open blocker{'s' if total_blockers != 1 else ''}, "
               f"{total_due} due soon ({today:%b %d})")
    html = (f"<div style='font-family:Arial,sans-serif;max-width:680px'><h2 style='color:#4D458A'>"
            f"Title Commitment Agent daily summary · {today:%A, %b %d}</h2>"
            + ("".join(blocks) or "<p>No open blockers and nothing due in the next 3 days.</p>")
            + "<p style='color:#767388;font-size:12px'>Total Cash Home Buyers · Title Commitment Agent</p></div>")
    return subject, html


# ---------------------------------------------------------------- the branded email
# The app's look (web/src/styles.css: TCHB indigo / red / green, Baloo 2 headings, Nunito Sans text, white cards on a
# soft grey page) in what email programs accept: tables and inline styles. Baloo 2 and Nunito Sans load where the
# email program allows web fonts (Apple Mail, iPhone); elsewhere (Gmail, Outlook) Arial stands in.
APP = "Title Commitment Agent"
SITE = "https://title.totalchb.com"
INDIGO, RED, GREEN, ORANGE = "#4D458A", "#BD2239", "#109648", "#B45309"
INK, BODY, MUTED, LINE, PAGE = "#211E33", "#47445A", "#767388", "#EEEDF2", "#F7F7F9"
RED_BG, GREEN_BG, ORANGE_BG, INDIGO_BG = "#FBF0F2", "#EAF7EF", "#FFF1E0", "#F5F4FA"
HEAD = "font-family:'Baloo 2','Nunito Sans',Arial,sans-serif;font-weight:700"
TEXT = "font-family:'Nunito Sans',Arial,sans-serif"
BAR = {"blocker": RED, "before": ORANGE, "fyi": INDIGO}
TAG = {"blocker": ("Closing Blocker", RED, RED_BG), "before": ("Before Closing", ORANGE, ORANGE_BG),
       "fyi": ("Review / FYI", INDIGO, INDIGO_BG)}


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def _chip(text: str, color: str, bg: str, size: int = 12) -> str:
    return (f'<span style="{HEAD};display:inline-block;font-size:{size}px;letter-spacing:.04em;color:{color};'
            f'background:{bg};border-radius:999px;padding:3px 10px;white-space:nowrap">{escape(text)}</span>')


def _button(href: str, label: str, color: str = RED) -> str:
    return (f'<a href="{escape(href)}" style="{HEAD};display:inline-block;font-size:15px;color:#ffffff;'
            f'background:{color};border-radius:999px;padding:10px 22px;text-decoration:none">{escape(label)}</a>')


def _due(i: ActionItem, today: date) -> str:
    if not i.due_date:
        return ""
    days = (date.fromisoformat(i.due_date) - today).days
    if days < 0:
        return _chip(f"Overdue · {_day(i.due_date)}", RED, RED_BG, 11)
    if days == 0:
        return _chip("Due today", ORANGE, ORANGE_BG, 11)
    return _chip(f"Due {_day(i.due_date)}", ORANGE if days <= SOON_DAYS else INDIGO,
                 ORANGE_BG if days <= SOON_DAYS else INDIGO_BG, 11)


def _dot(color: str) -> str:
    return f'<span style="display:inline-block;width:9px;height:9px;border-radius:9px;background:{color}"></span>'


def _row(i: ActionItem, today: date) -> str:
    """One item, one line: a dot in the priority's color, the headline, and the due date on the right."""
    return (f'<tr><td width="16" valign="top" style="padding:7px 0 0">{_dot(BAR.get(i.priority, INDIGO))}</td>'
            f'<td valign="top" style="{TEXT};font-size:14px;line-height:1.4;color:{INK};padding:3px 8px 3px 0">'
            f"{escape(i.title)}</td>"
            f'<td valign="top" align="right" style="padding:2px 0;white-space:nowrap">{_due(i, today)}</td></tr>')


def _closing(d: dict, today: date) -> str:
    if not d.get("closing_date"):
        return _chip("No closing date", MUTED, LINE)
    days = (date.fromisoformat(d["closing_date"]) - today).days
    text = (f"{-days}d past closing" if days < 0 else "Closing today" if days == 0
            else f"Closing {_day(d['closing_date'])} · {days}d")
    return _chip(text, RED if days < 0 else ORANGE if days <= 7 else INDIGO,
                 RED_BG if days < 0 else ORANGE_BG if days <= 7 else INDIGO_BG)


def _table(rows: str, style: str = "") -> str:
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:separate;{style}">{rows}</table>')


def _deal(d: dict, rows: list[ActionItem], blockers: int, today: date, base: str) -> str:
    """A deal at a glance: the address (a link to the deal) and its closing chip, its details, then one line per
    open Closing Blocker or item due soon."""
    name = escape(d.get("address") or f"Deal {d['id']}")
    href = f"{base}/#/deal/{d['id']}"
    if base:
        name = f'<a href="{escape(href)}" style="color:{INDIGO};text-decoration:none">{name}</a>'
    meta = " · ".join(x for x in (d.get("deal_type"), f"TC {d.get('tc') or 'unassigned'}") if x)
    count = (f'<b style="color:{RED}">{blockers} open blocker{"s" if blockers != 1 else ""}</b>' if blockers
             else f'<b style="color:{GREEN}">No blockers</b>')
    head = _table(
        f'<tr><td valign="top" style="{HEAD};font-size:17px;line-height:1.3;padding-right:8px">{name}</td>'
        f'<td valign="top" align="right" style="white-space:nowrap">{_closing(d, today)}</td></tr>')
    link = (f'<div style="padding-top:8px;text-align:right"><a href="{escape(href)}" style="{HEAD};font-size:14px;'
            f'color:{RED};text-decoration:none">Open The Deal &rarr;</a></div>' if base else "")
    card = (f'<tr><td style="padding:14px 16px">{head}'
            f'<div style="{TEXT};font-size:13px;color:{MUTED};padding:2px 0 8px">{escape(meta)} · {count}</div>'
            f'<div style="border-top:1px solid {LINE};padding-top:6px">'
            f'{_table("".join(_row(i, today) for i in rows))}</div>{link}</td></tr>')
    return (f'<tr><td style="padding:0 0 12px">'
            f'{_table(card, f"background:#ffffff;border:1px solid {LINE};border-radius:14px")}</td></tr>')


def _stat(value: int, label: str, color: str) -> str:
    return (f'<td width="25%" align="center" style="padding:12px 4px;background:#ffffff;border:1px solid {LINE};'
            f'border-radius:12px"><div style="{HEAD};font-size:28px;line-height:1;color:{color}">{value}</div>'
            f'<div style="{TEXT};font-size:12px;color:{MUTED};padding-top:4px">{escape(label)}</div></td>')


def _note(text: str) -> str:
    return (f'<tr><td style="padding:8px 0 16px"><div style="{TEXT};font-size:15px;color:{BODY};'
            f'background:{GREEN_BG};border-radius:12px;padding:16px">{escape(text)}</div></td></tr>')


def _on_track(d: dict, base: str) -> str:
    name = escape(d.get("address") or f"Deal {d['id']}")
    if base:
        name = (f'<a href="{escape(base)}/#/deal/{d["id"]}" style="color:{INDIGO};font-weight:700;'
                f'text-decoration:none">{name}</a>')
    else:
        name = f"<b>{name}</b>"
    closing = f" · closing {_day(d['closing_date'])}" if d.get("closing_date") else ""
    return (f'<tr><td style="{TEXT};font-size:14px;color:{BODY};padding:3px 0"><span style="color:{GREEN}">'
            f'&#10003;</span> {name} <span style="color:{MUTED}">· nothing due{closing}</span></td></tr>')


FONTS = ("https://fonts.googleapis.com/css2?family=Baloo+2:wght@700&amp;family=Nunito+Sans:wght@400;700"
         "&amp;display=swap")


def branded_html(deals: list[dict], items_by_deal: dict[int, list[ActionItem]], today: date,
                 app_url: str = "") -> tuple[str, str]:
    """(subject, html): every open deal's open Closing Blockers and anything due in the next 3 days, in the app's
    design. Deals with nothing to report are listed at the end, so every open deal shows."""
    soon = (today + timedelta(days=SOON_DAYS)).isoformat()
    base = app_url.rstrip("/")
    cards, quiet = [], []
    total_blockers = total_due = overdue = 0
    for d in deals:
        items = _open(items_by_deal.get(d["id"], []))
        blockers = [i for i in items if i.priority == "blocker"]
        due = [i for i in items if i.due_date and i.due_date <= soon]
        total_blockers += len(blockers)
        total_due += len(due)
        overdue += sum(1 for i in items if i.due_date and i.due_date < today.isoformat())
        rows = sorted(blockers + [x for x in due if x not in blockers],
                      key=lambda x: (x.priority != "blocker", x.due_date or "9999"))
        if rows:
            cards.append(_deal(d, rows, len(blockers), today, base))
        else:
            quiet.append(d)
    subject = (f"{APP}: {total_blockers} open blocker{'s' if total_blockers != 1 else ''}, "
               f"{total_due} due soon ({today:%b %d})")
    preheader = (f"{total_blockers} open Closing Blocker{'s' if total_blockers != 1 else ''} across {len(deals)} open "
                 f"deal{'s' if len(deals) != 1 else ''} · {total_due} due in the next {SOON_DAYS} days"
                 + (f" · {overdue} overdue" if overdue else ""))
    if not deals:
        body = _note("No open deals today. Analyze a commitment to start one.")
    elif not cards:
        body = _note(f"No open Closing Blockers and nothing due in the next {SOON_DAYS} days.")
    else:
        body = "".join(cards)
    if quiet:
        body += (f'<tr><td style="{HEAD};font-size:17px;color:{INDIGO};padding:4px 0 6px">On Track</td></tr>'
                 + "".join(_on_track(d, base) for d in quiet))
    stats = (_stat(len(deals), "Open Deals", INDIGO)
             + _stat(total_blockers, "Open Blockers", RED if total_blockers else GREEN)
             + _stat(total_due, "Due Soon", ORANGE if total_due else GREEN)
             + _stat(overdue, "Overdue", RED if overdue else GREEN))
    header = _table(
        f'<tr><td><img src="{escape(base or SITE)}/logo-full.png" width="150" height="46" '
        f'alt="Total Cash Home Buyers" style="display:block;border:0"></td>'
        f'<td align="right" style="{HEAD};font-size:12px;letter-spacing:.08em;text-transform:uppercase;'
        f'color:{INDIGO}">Daily Summary</td></tr>')
    hero = (f'<div style="{HEAD};font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:{RED}">'
            f"{today:%A}, {today:%B} {today.day}</div>"
            f'<div style="{HEAD};font-size:30px;line-height:1.2;color:{INDIGO};padding-top:4px">'
            f'Title Commitment <span style="color:{RED}">Agent</span></div>'
            f'<div style="{TEXT};font-size:15px;color:{BODY};padding-top:6px">Every open deal\'s Closing Blockers '
            f"and anything due in the next {SOON_DAYS} days.</div>")
    footer = (f"Sent weekdays at 8:00 AM Eastern to the team list in Settings. Closing Blockers are also in the "
              f"Universal Team Hub.<br>Total Cash Home Buyers · {APP} · Internal use only")
    rows = (
        f'<tr><td style="background:#ffffff;border-radius:20px 20px 0 0;padding:18px 24px;'
        f'border-bottom:1px solid {LINE}">{header}</td></tr>'
        f'<tr><td style="background:#ffffff;padding:24px 24px 8px">{hero}</td></tr>'
        f'<tr><td style="background:#ffffff;padding:12px 18px 8px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="6" style="border-collapse:separate">'
        f"<tr>{stats}</tr></table></td></tr>"
        f'<tr><td style="background:#ffffff;padding:0 24px 10px;{TEXT};font-size:12px;color:{MUTED}">'
        f"{_dot(RED)} Closing Blocker &nbsp; {_dot(ORANGE)} Before Closing, due soon &nbsp; "
        f"Tap an address to open the deal.</td></tr>"
        f'<tr><td style="background:{INDIGO_BG};padding:16px 16px 6px">{_table(body)}</td></tr>'
        f'<tr><td align="center" style="background:#ffffff;border-radius:0 0 20px 20px;padding:20px 24px 26px">'
        f'{_button(f"{base}/" if base else SITE, f"Open The {APP}", INDIGO)}</td></tr>'
        f'<tr><td align="center" style="{TEXT};font-size:12px;line-height:1.6;color:{MUTED};padding:18px 12px 0">'
        f"{footer}</td></tr>")
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">'
        f'<title>{escape(subject)}</title><link href="{FONTS}" rel="stylesheet"></head>'
        f'<body style="margin:0;padding:0;background:{PAGE}">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(preheader)}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAGE}"><tr>'
        f'<td align="center" style="padding:24px 12px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px">{rows}'
        "</table></td></tr></table></body></html>")
    return subject, html


def send(api_key: str, sender: str, recipients: list[str], subject: str, html: str,
         deliver_at: datetime | None = None) -> None:
    """Sends now, or hands the email to Resend to deliver at deliver_at."""
    if not recipients:
        raise ValueError("No recipients set (Settings → Daily email).")
    body = {"from": f"Title Commitment Agent <{sender}>", "to": recipients, "subject": subject, "html": html}
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
