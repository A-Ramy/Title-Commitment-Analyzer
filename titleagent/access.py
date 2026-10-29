"""Who may use the app. The deals hold personal data and every review spends AI credit: the engine checks every
request's Firebase sign-in (engine/main.py) and lets in only these accounts."""

from __future__ import annotations


def email_allowed(email: str | None, emails: tuple[str, ...], domains: tuple[str, ...]) -> bool:
    """Listed email, or an email at a listed domain (exact domain match: 'evil-totalchb.com' is not 'totalchb.com')."""
    if not email or "@" not in email:
        return False
    email = email.strip().lower()
    return email in emails or email.rsplit("@", 1)[1] in domains
