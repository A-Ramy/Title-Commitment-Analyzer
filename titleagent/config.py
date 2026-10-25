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

    @property
    def has_ai(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_google(self) -> bool:
        return self.google_service_account is not None


def _streamlit_secrets() -> dict:
    """Streamlit secrets if running under Streamlit and a secrets file exists; else {}."""
    try:
        import streamlit as st

        return dict(st.secrets)
    except Exception:
        return {}


def _decode_service_account(raw_b64: str | None, table: dict | None) -> dict | None:
    if table:
        return dict(table)
    if not raw_b64:
        return None
    try:
        return json.loads(base64.b64decode(raw_b64).decode("utf-8"))
    except Exception as exc:  # never echo the value itself
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON_B64 is set but is not valid base64-encoded JSON.") from exc


def load_secrets() -> Secrets:
    load_dotenv(ROOT / ".env", override=False)
    st_secrets = _streamlit_secrets()

    def get(key: str) -> str | None:
        return os.environ.get(key) or (str(st_secrets[key]) if key in st_secrets else None) or None

    return Secrets(
        anthropic_api_key=get("ANTHROPIC_API_KEY"),
        database_url=get("DATABASE_URL"),
        google_service_account=_decode_service_account(
            get("GOOGLE_SERVICE_ACCOUNT_JSON_B64"), st_secrets.get("gcp_service_account")
        ),
        resend_api_key=get("RESEND_API_KEY"),
    )


def demo_mode() -> bool:
    """Developer preview with a made-up sample deal and no AI calls (TITLE_AGENT_DEMO=1)."""
    return os.environ.get("TITLE_AGENT_DEMO") == "1"
