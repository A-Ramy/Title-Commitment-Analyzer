"""Send the daily summary. Run on a schedule (.github/workflows/daily-email.yml) with DATABASE_URL and
RESEND_API_KEY set; APP_URL (optional) adds an "Open" link per deal.

    uv run python scripts/daily_email.py [--dry-run]
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titleagent.config import load_secrets  # noqa: E402
from titleagent.emailer import send, summary_html  # noqa: E402
from titleagent.storage import Store  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    store = Store(secrets.database_url)
    settings = store.get_settings()
    subject, html = summary_html(store.list_deals(status="open"), store.open_items_by_deal(), date.today(),
                                 os.environ.get("APP_URL", ""))
    if "--dry-run" in sys.argv:
        print(subject)
        print(html)
        return 0
    if not secrets.resend_api_key:
        print("RESEND_API_KEY is not set.", file=sys.stderr)
        return 1
    send(secrets.resend_api_key, settings["email_from"], settings["email_recipients"], subject, html)
    print(f"Sent to {len(settings['email_recipients'])} recipient(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
