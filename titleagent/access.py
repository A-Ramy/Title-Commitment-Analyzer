"""Who may open the app. The deals hold personal data and every review spends AI credit, so access is denied unless
a sign-in method is configured and the person passes it."""

from __future__ import annotations

import base64
import hashlib
import hmac


def email_allowed(email: str | None, emails: tuple[str, ...], domains: tuple[str, ...]) -> bool:
    """Listed email, or an email at a listed domain (exact domain match: 'evil-totalchb.com' is not 'totalchb.com')."""
    if not email or "@" not in email:
        return False
    email = email.strip().lower()
    return email in emails or email.rsplit("@", 1)[1] in domains


def password_ok(given: str, expected: str | None) -> bool:
    return bool(expected) and hmac.compare_digest(given.encode(), expected.encode())


# ---- remembered sign-in: a signed pass kept in a browser cookie, so a reload or a link from the daily email does
# not ask for the password again. Signed with the team password: changing APP_PASSWORD signs everyone out.
PASS_COOKIE = "title_agent_pass"
PASS_DAYS = 30


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), b"title-agent-pass|" + payload.encode(), hashlib.sha256).hexdigest()


def make_pass(email: str, secret: str, now: float, days: int = PASS_DAYS) -> str:
    payload = f"{base64.urlsafe_b64encode(email.encode()).decode()}.{int(now + days * 86400)}"
    return f"{payload}.{_sign(payload, secret)}"


def read_pass(token: str | None, secret: str | None, now: float) -> str | None:
    """The email in a valid, unexpired pass; None for anything else (missing, tampered, expired, old password)."""
    if not token or not secret or token.count(".") != 2:
        return None
    email_b64, expiry, sig = token.split(".")
    payload = f"{email_b64}.{expiry}"
    if not hmac.compare_digest(sig, _sign(payload, secret)):
        return None
    try:
        if int(expiry) < now:
            return None
        email = base64.urlsafe_b64decode(email_b64.encode()).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    return email if "@" in email else None
