"""The daily summary email, from GitHub Actions: the backup for the 8:00 AM send (.github/workflows/daily-email.yml).

The engine sends it at 8:00 AM Eastern on weekdays when Google Cloud Scheduler calls it (titleagent/daily.py,
scripts/scheduler_setup.sh). GitHub starts scheduled runs late or skips them, so it only backs that up: its runs are
later in the morning and send only if nothing went out yet. Needs FIREBASE_PROJECT_ID, FIREBASE_SERVICE_ACCOUNT_JSON
and RESEND_API_KEY; APP_URL adds the links to each deal.

    uv run python scripts/daily_email.py [--dry-run] [--now] [--check]

--now sends immediately, even if today's email already went out (manual runs from GitHub use it, to test).
--check sends nothing and prints only where the data comes from and how links look (Run workflow → check only).
--dry-run prints the email (it holds deal details: never in the public Actions logs).
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titleagent.config import load_secrets  # noqa: E402
from titleagent.daily import send_summary  # noqa: E402
from titleagent.emailer import EASTERN, summary_html  # noqa: E402
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

    _, message = send_summary(store, secrets, now, os.environ.get("APP_URL", ""), force="--now" in sys.argv)
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
