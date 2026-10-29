"""Send the daily summary at 8:00 AM Eastern on weekdays. Run on a schedule (.github/workflows/daily-email.yml) with
FIREBASE_PROJECT_ID, FIREBASE_SERVICE_ACCOUNT_JSON and RESEND_API_KEY set; APP_URL adds an "Open" link per deal.

GitHub's scheduler runs hours late or skips runs, so the workflow tries several times in the early morning: the first
run that gets through hands the email to Resend to deliver at 8:00 sharp, and later runs see it's done. A run after
7:58 sends right away. Each run's outcome is saved in the app database so Settings can show it (the app itself never
holds the Resend key).

    uv run python scripts/daily_email.py [--dry-run] [--now] [--check]

--now sends immediately, even if today's email already went out (manual runs from GitHub use it, to test).
--check sends nothing and prints only where the data comes from and how links look (Run workflow → check only).
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titleagent.config import load_secrets  # noqa: E402
from titleagent.emailer import EASTERN, LAST_RUN, already_done, plan, run_record, send, summary_html  # noqa: E402
from titleagent.storage import open_store  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    if not secrets.has_data_store:  # not set up: skip quietly instead of failing (and emailing a failure notice)
        print("Skipped: FIREBASE_PROJECT_ID and FIREBASE_SERVICE_ACCOUNT_JSON must be set as GitHub Actions secrets.")
        return 0
    store = open_store(secrets)
    settings = store.get_settings()
    now = datetime.now(UTC)
    day = now.astimezone(EASTERN).date()
    subject, html = summary_html(store.list_deals(status="open"), store.open_items_by_deal(), day,
                                 os.environ.get("APP_URL", ""))
    if "--dry-run" in sys.argv:
        print(subject)
        print(html)
        return 0
    if "--check" in sys.argv:  # safe for public logs: where the data comes from and the link style, no deal details
        source = f"Firestore ({secrets.firebase_project})"
        base = os.environ.get("APP_URL", "").rstrip("/") or "(APP_URL not set)"
        print(f"Data: {source} · open deals: {len(store.list_deals(status='open'))} · "
              f"links: {base}/#/deal/<id> · "
              f"recipients: {len(settings['email_recipients'])} · Resend key set: {bool(secrets.resend_api_key)}")
        return 0

    force_now = "--now" in sys.argv
    action, deliver_at = ("now", None) if force_now else plan(now)
    if action == "skip":
        print("Weekend: no email.")
        return 0
    if not force_now and already_done(settings.get(LAST_RUN), day):
        print(f"Today's email ({day}) is already sent or scheduled.")
        return 0

    def record(result: str, detail: str) -> None:
        store.set_setting(LAST_RUN, run_record(result, detail, now, day, deliver_at), by="daily email")

    if not secrets.resend_api_key:
        print("Skipped: RESEND_API_KEY must be set as a GitHub Actions secret.")
        record("skipped", "RESEND_API_KEY is not set in GitHub")
        return 0
    recipients = settings["email_recipients"]
    if not recipients:
        print("Skipped: no recipients yet (app → Settings → Daily Email → Send to).")
        record("skipped", "no recipients in Settings")
        return 0
    try:
        send(secrets.resend_api_key, settings["email_from"], recipients, subject, html, deliver_at)
    except Exception as exc:
        record("failed", str(exc)[:200])  # the next run this morning tries again
        raise
    count = f"{len(recipients)} recipient{'s' if len(recipients) != 1 else ''}"
    if deliver_at:
        record("scheduled", count)
        print(f"Scheduled for {deliver_at:%Y-%m-%d %H:%M %Z} to {count}.")
    else:
        record("test" if force_now else "sent", count)  # a test doesn't stand in for the 8:00 email
        print(f"Sent to {count}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
