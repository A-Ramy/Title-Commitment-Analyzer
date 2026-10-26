"""Who may open the app. The deals hold personal data and every review spends AI credit, so access is denied unless
a sign-in method is configured and the person passes it."""

from __future__ import annotations

import hmac


def email_allowed(email: str | None, emails: tuple[str, ...], domains: tuple[str, ...]) -> bool:
    """Listed email, or an email at a listed domain (exact domain match: 'evil-totalchb.com' is not 'totalchb.com')."""
    if not email or "@" not in email:
        return False
    email = email.strip().lower()
    return email in emails or email.rsplit("@", 1)[1] in domains


def password_ok(given: str, expected: str | None) -> bool:
    return bool(expected) and hmac.compare_digest(given.encode(), expected.encode())
