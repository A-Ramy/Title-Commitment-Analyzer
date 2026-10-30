"""The morning run: today's summary email (emailer.py), then the Team Hub catch-up (hub.py).

Google Cloud Scheduler calls the engine at 8:00 AM Eastern on weekdays (POST /v1/tasks/morning, set up once with
scripts/scheduler_setup.sh), which sends the email at once. GitHub Actions runs later in the morning as a backup
(scripts/daily_email.py, .github/workflows/daily-email.yml): it sends only if nothing went out yet. Every outcome is
saved in the app database, so Settings shows it and a second run doesn't send twice. Messages say counts, never deal
details (the Actions logs are public).
"""

from __future__ import annotations

from datetime import datetime

from titleagent import hub
from titleagent.emailer import EASTERN, LAST_RUN, already_done, plan, run_record, send, summary_html


def send_summary(store, secrets, now: datetime, app_url: str, force: bool = False) -> tuple[str, str]:
    """(result, message). result: weekend | done | skipped | scheduled | sent | test. Raises when the email service
    fails (recorded as failed, so the next try sends it). force sends now, even if today's went out (a test)."""
    day = now.astimezone(EASTERN).date()
    action, deliver_at = ("now", None) if force else plan(now)
    if action == "skip":
        return "weekend", "Weekend: no email."
    settings = store.get_settings()
    if not force and already_done(settings.get(LAST_RUN), day):
        return "done", f"Today's email ({day}) is already sent or scheduled."

    def record(result: str, detail: str) -> None:
        store.set_setting(LAST_RUN, run_record(result, detail, now, day, deliver_at), by="daily email")

    if not secrets.resend_api_key:
        record("skipped", "RESEND_API_KEY is not set")
        return "skipped", "Skipped: RESEND_API_KEY is not set."
    recipients = settings["email_recipients"]
    if not recipients:
        record("skipped", "no recipients in Settings")
        return "skipped", "Skipped: no recipients yet (app → Settings → Daily Email → Send To)."
    subject, html = summary_html(store.list_deals(status="open"), store.open_items_by_deal(), day, app_url)
    try:
        send(secrets.resend_api_key, settings["email_from"], recipients, subject, html, deliver_at)
    except Exception as exc:
        record("failed", str(exc)[:200])
        raise
    count = f"{len(recipients)} recipient{'s' if len(recipients) != 1 else ''}"
    if deliver_at:
        record("scheduled", count)
        return "scheduled", f"Scheduled for {deliver_at:%Y-%m-%d %H:%M %Z} to {count}."
    result = "test" if force else "sent"  # a test doesn't stand in for the day's email
    record(result, count)
    return result, f"Sent to {count}."


def hub_catch_up(store, secrets, app_url: str) -> dict:
    """Every open deal's Closing Blockers to the Team Hub, and back what changed there. Counts only."""
    out = {"deals": 0, "synced": 0, "new_tasks": 0, "copied_back": 0, "failed": 0}
    if not getattr(secrets, "has_hub", False):
        return out
    for d in store.list_deals(status="open"):
        out["deals"] += 1
        try:
            r = hub.sync(store, secrets, d["id"], app_url)
        except Exception:  # the next change or tomorrow's run catches it up
            out["failed"] += 1
            continue
        out["synced"] += 1
        out["new_tasks"] += int(r.get("created", False))
        out["copied_back"] += r.get("applied", 0)
    return out
