"""Every open deal's Closing Blockers to the Universal Team Hub, and back what changed there (GitHub Actions, each
weekday morning with the daily email run). Prints counts only.

    uv run python scripts/hub_sync.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from titleagent import hub  # noqa: E402
from titleagent.config import load_secrets  # noqa: E402
from titleagent.storage import open_store  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    if not secrets.has_hub:
        print("Hub not set up (HUB_SYNC_SECRET missing): nothing to do.")
        return 0
    store = open_store(secrets)
    app_url = os.environ.get("APP_URL") or hub.APP_URL
    deals = store.list_deals(status="open")
    ok = failed = created = applied = 0
    for d in deals:
        try:
            r = hub.sync(store, secrets, d["id"], app_url)
            ok += 1
            created += int(r.get("created", False))
            applied += r.get("applied", 0)
        except Exception as exc:
            failed += 1
            # the reason (e.g. the hub's address or status code) says nothing about the deal itself
            reason = str(exc).split("(Caused by")[-1].strip(" )")[:160] if str(exc) else ""
            print(f"one deal failed: {type(exc).__name__} {reason}")
    print(f"open deals {len(deals)}: synced {ok}, new hub tasks {created}, "
          f"hub changes copied back {applied}, failed {failed}")
    return 1 if failed and not ok else 0


if __name__ == "__main__":
    sys.exit(main())
