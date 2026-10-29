"""Configuration: secrets come from env vars / .env first, then Streamlit secrets.

Team settings (admins, TCs, due-date offsets, email recipients...) have defaults here and are overridden by values
saved in the app's own database (see storage.py).
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
    # Company names that mean "our own entity" in a chain of title (double close / assignment checks).
    "our_entities": ["Total Cash Home Buyers, LLC", "Total Cash Home Buyers LLC"],
}


@dataclass(frozen=True)
class Secrets:
    anthropic_api_key: str | None
    database_url: str | None
    google_service_account: dict | None
    resend_api_key: str | None
    # Firebase (v2): when FIREBASE_PROJECT_ID is set the app's data lives in Firestore + Storage instead of the
    # SQL database. Credentials: the service account key pasted as-is, or Google's default credentials (Cloud Run).
    firebase_project: str | None = None
    firebase_bucket: str | None = None
    firebase_credentials: dict | None = None
    # Google exports through the Apps Script web app (titleagent/exports/google_export.gs): the easy setup
    google_export_url: str | None = None
    google_export_key: str | None = None
    # Who may open the app (see ui/auth.py). Google sign-in when the [auth] section is set, else the team password.
    google_login: bool = False
    app_password: str | None = None
    allowed_emails: tuple[str, ...] = ()
    allowed_domains: tuple[str, ...] = ("totalchb.com",)
    no_login: bool = False  # local development only: TITLE_AGENT_NO_LOGIN=1

    @property
    def has_ai(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_data_store(self) -> bool:
        """A real database is configured (Firestore or SQL), not the local file."""
        return bool(self.firebase_project or self.database_url)

    @property
    def has_google(self) -> bool:
        return bool(self.google_export_url and self.google_export_key) or self.google_service_account is not None


def _streamlit_secrets() -> dict:
    """Streamlit secrets if running under Streamlit and a secrets file exists; else {}."""
    try:
        import streamlit as st

        return dict(st.secrets)
    except Exception:
        return {}


def _decode_service_account(raw_b64: str | None, table: dict | None, raw_json: str | None = None) -> dict | None:
    if table:
        return dict(table)
    if raw_json:  # the key file pasted as-is between  in the Streamlit secrets
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
    st_secrets = _streamlit_secrets()

    def get(key: str) -> str | None:
        return os.environ.get(key) or (str(st_secrets[key]) if key in st_secrets else None) or None

    def listed(key: str, default: str = "") -> tuple[str, ...]:
        return tuple(x.strip().lower() for x in (get(key) or default).replace(";", ",").split(",") if x.strip())

    auth = st_secrets.get("auth") or {}
    return Secrets(
        google_login=bool(auth.get("client_id") and auth.get("redirect_uri") and auth.get("cookie_secret")),
        app_password=get("APP_PASSWORD"),
        allowed_emails=listed("ALLOWED_EMAILS"),
        allowed_domains=listed("ALLOWED_DOMAINS", "totalchb.com"),
        no_login=os.environ.get("TITLE_AGENT_NO_LOGIN") == "1",
        anthropic_api_key=get("ANTHROPIC_API_KEY"),
        database_url=get("DATABASE_URL"),
        google_service_account=_decode_service_account(
            get("GOOGLE_SERVICE_ACCOUNT_JSON_B64"), st_secrets.get("gcp_service_account"),
            get("GOOGLE_SERVICE_ACCOUNT_JSON"),
        ),
        resend_api_key=get("RESEND_API_KEY"),
        firebase_project=get("FIREBASE_PROJECT_ID"),
        firebase_bucket=get("FIREBASE_STORAGE_BUCKET"),
        firebase_credentials=_firebase_credentials(get("FIREBASE_SERVICE_ACCOUNT_JSON")),
        google_export_url=get("GOOGLE_EXPORT_URL"),
        google_export_key=get("GOOGLE_EXPORT_KEY"),
    )


def demo_mode() -> bool:
    """Developer preview with a made-up sample deal and no AI calls (TITLE_AGENT_DEMO=1)."""
    return os.environ.get("TITLE_AGENT_DEMO") == "1"
