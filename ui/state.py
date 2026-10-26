"""Cached access to secrets, storage and the AI, and who is using the app."""

from __future__ import annotations

import streamlit as st

from titleagent.config import Secrets, demo_mode, load_secrets
from titleagent.llm import LLM, ClaudeLLM
from titleagent.storage import Store


@st.cache_resource
def get_secrets() -> Secrets:
    return load_secrets()


@st.cache_resource
def get_store() -> Store:
    return Store(get_secrets().database_url)


def get_settings() -> dict:
    return get_store().get_settings()


def get_llm() -> LLM:
    if demo_mode():
        from titleagent import demo

        return demo.scripted_llm()
    return ClaudeLLM(get_secrets().anthropic_api_key or "")


def ai_ready() -> bool:
    return demo_mode() or get_secrets().has_ai


def user_email() -> str:
    """The signed-in person (ui/auth.py); empty when running locally without a login."""
    from ui.auth import signed_in_email

    return signed_in_email()


def who() -> str:
    return user_email() or "local user"


def is_admin() -> bool:
    """Admins approve lessons and change settings. No admins set yet = everyone (first-time setup)."""
    admins = [a.strip().lower() for a in get_settings().get("admins", []) if a.strip()]
    return not admins or user_email().lower() in admins
