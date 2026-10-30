"""Configuration: secrets come from environment variables (Cloud Run, GitHub Actions) or a local .env file.

Team settings (admins, TCs, due-date offsets, email recipients...) have defaults here and are overridden by values
saved in Firestore (Settings in the app).
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / ".data"

MODEL = "claude-opus-5-5"  # accuracy first (owner, 2026-10-24)
EFFORT = "high"

DEAL_TYPES = [
    "Wholesale (Assignment)",
    "Double Close",
    "Novation / Listing",
    "Fix & Flip",
    "Buy & Hold",
    "Subject-To",
    "Seller Financing",
]

# Editable in Settings; stored in the app database. Keys are stable identifiers.
DEFAULT_SETTINGS: dict = {
    # Emails of the people who approve lessons (owner, CTO, TC, TC assistant). Empty = everyone is an admin (setup).
    "admins": [],
    # Transaction coordinators: every item's owner is the deal's TC.
    "tcs": [],
    # Daily summary recipients (all users, owner 2026-10-25).
    "email_recipients": [],
    "email_from": "title-agent@totalchb.com",
    # Days before closing each kind of item is due (weekends move back to Friday).
    "due_offsets": {"payoff": 10, "curative": 14, "documents": 5, "bring_down": 5, "closing": 0},
    "google_folder_id": "",
    # What Team Leaders and Members may do (Settings → Permissions; owner 2026-10-30). Managers can do everything.
    # approve_lessons: the Feedback Inbox and the lessons (Knowledge); report_missing: Report Missing Item on a deal.
    "permissions": {"lead": {"approve_lessons": True, "report_missing": True},
                    "member": {"approve_lessons": False, "report_missing": True}},
    # Company names that mean "our own entity" in a chain of title (double close / assignment checks).
    "our_entities": ["Total Cash Home Buyers, LLC", "Total Cash Home Buyers LLC"],
}

# The Team tab (owner 2026-10-30, as in the Universal Team Hub): name, sign-in email, role, department and photo.
# Managers are the admins; everyone in TC is in the TC list. The team lives only in the app's database
# (settings/team): names and emails stay out of this public repository.
TEAM_ROLES = ("manager", "lead", "member")  # Manager, Team Leader, Member
TEAM_DEPTS = ("TC",)
PERMISSIONS = ("approve_lessons", "report_missing")

@dataclass(frozen=True)
class Secrets:
    anthropic_api_key: str | None
    google_service_account: dict | None
    resend_api_key: str | None
    # Firebase: the app's data (Firestore + Storage). Credentials: the service account key as-is (GitHub Actions),
    # or Google's default credentials (the engine on Cloud Run).
    firebase_project: str | None = None
    firebase_bucket: str | None = None
    firebase_credentials: dict | None = None
    # Google exports through the Apps Script web app (titleagent/exports/google_export.gs): the easy setup
    google_export_url: str | None = None
    google_export_key: str | None = None
    # Who may use the app (the engine checks every request's Firebase sign-in against these)
    allowed_emails: tuple[str, ...] = ()
    allowed_domains: tuple[str, ...] = ("totalchb.com",)
    # The Universal Team Hub (titleagent/hub.py): where Closing Blockers go, and the secret both apps sign with
    hub_url: str | None = None
    hub_secret: str | None = None
    # The morning run (titleagent/daily.py): Google Cloud Scheduler calls the engine with a Google-signed token for
    # this audience (the engine's address), from this service account (scripts/scheduler_setup.sh)
    tasks_audience: str | None = None
    tasks_caller: str | None = None

    @property
    def has_ai(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_hub(self) -> bool:
        return bool(self.hub_url and self.hub_secret)

    @property
    def has_data_store(self) -> bool:
        return bool(self.firebase_project)

    @property
    def has_google(self) -> bool:
        return bool(self.google_export_url and self.google_export_key) or self.google_service_account is not None


def _decode_service_account(raw_b64: str | None, raw_json: str | None = None) -> dict | None:
    if raw_json:  # the key file's JSON as-is
        try:
            return json.loads(raw_json)
        except Exception as exc:  # never echo the value itself
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is set but is not the key file's JSON.") from exc
    if not raw_b64:
        return None
    try:
        return json.loads(base64.b64decode(raw_b64).decode("utf-8"))
    except Exception as exc:  # never echo the value itself
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON_B64 is set but is not valid base64-encoded JSON.") from exc


def _firebase_credentials(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception as exc:  # never echo the value itself
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON is set but is not the key file's JSON.") from exc


def load_secrets() -> Secrets:
    load_dotenv(ROOT / ".env", override=False)

    def get(key: str) -> str | None:
        return os.environ.get(key) or None

    def listed(key: str, default: str = "") -> tuple[str, ...]:
        return tuple(x.strip().lower() for x in (get(key) or default).replace(";", ",").split(",") if x.strip())

    return Secrets(
        allowed_emails=listed("ALLOWED_EMAILS"),
        allowed_domains=listed("ALLOWED_DOMAINS", "totalchb.com"),
        anthropic_api_key=get("ANTHROPIC_API_KEY"),
        google_service_account=_decode_service_account(get("GOOGLE_SERVICE_ACCOUNT_JSON_B64"),
                                                       get("GOOGLE_SERVICE_ACCOUNT_JSON")),
        resend_api_key=get("RESEND_API_KEY"),
        firebase_project=get("FIREBASE_PROJECT_ID"),
        firebase_bucket=get("FIREBASE_STORAGE_BUCKET"),
        firebase_credentials=_firebase_credentials(get("FIREBASE_SERVICE_ACCOUNT_JSON")),
        google_export_url=get("GOOGLE_EXPORT_URL"),
        google_export_key=get("GOOGLE_EXPORT_KEY"),
        hub_url=get("HUB_URL") or ("https://hub.totalchb.com/api/title-agent" if get("HUB_SYNC_SECRET") else None),
        hub_secret=get("HUB_SYNC_SECRET"),
        tasks_audience=get("TASKS_AUDIENCE"),
        tasks_caller=get("TASKS_CALLER"),
    )


def demo_mode() -> bool:
    """Developer preview with a made-up sample deal and no AI calls (TITLE_AGENT_DEMO=1)."""
    return os.environ.get("TITLE_AGENT_DEMO") == "1"
