"""The sign-in gate, run before any page. Streamlit Community Cloud allows one private app per account (the
Projection Tool has it), so this app is public on the web and protects itself:

1. Google sign-in (st.login) when the [auth] secrets are set: only ALLOWED_EMAILS and @ALLOWED_DOMAINS get in.
2. Otherwise the team password (APP_PASSWORD), as a stopgap.
3. Neither set: locked. Local development opts out with TITLE_AGENT_NO_LOGIN=1 (the demo needs no login).
"""

from __future__ import annotations

import json
import time
from urllib.parse import unquote

import streamlit as st
import streamlit.components.v1 as components

from titleagent.access import PASS_COOKIE, PASS_DAYS, email_allowed, make_pass, password_ok, read_pass
from titleagent.config import demo_mode
from ui.brand import logo
from ui.state import get_secrets


def _frame(title: str):
    st.html("<style>[data-testid=stSidebar],[data-testid=stSidebarCollapsedControl]{display:none!important}</style>")
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.html('<div style="height:10vh"></div>')
        st.image(logo(), width="stretch")
        st.html(f'<div class="brand-sub" style="text-align:center;margin-top:8px">{title}</div>')
    return mid


def signed_in_email() -> str:
    """The verified email of the person using the app ('' when signed in by password or not at all)."""
    if get_secrets().google_login:
        try:
            return str(st.user.get("email") or "") if st.user.is_logged_in else ""
        except Exception:
            return ""
    return str(st.session_state.get("pw_email") or "")


def gate() -> None:
    """Stops the page unless the person is allowed in."""
    s = get_secrets()
    if demo_mode() or s.no_login:
        return

    if s.google_login:
        if not st.user.is_logged_in:
            mid = _frame("Title Agent · sign in with your company Google account")
            with mid:
                st.button("Sign In With Google", type="primary", icon=":material/login:", width="stretch",
                          on_click=st.login)
            st.stop()
        email = str(st.user.get("email") or "")
        verified = st.user.get("email_verified", True)
        if not (verified and email_allowed(email, s.allowed_emails, s.allowed_domains)):
            mid = _frame("Title Agent")
            with mid:
                st.error(f"{email or 'This account'} doesn't have access. Ask an admin to add you, then sign in again.")
                st.button("Sign Out", on_click=st.logout, width="stretch")
            st.stop()
        return

    if s.app_password:
        if not st.session_state.get("pw_ok") and not st.session_state.get("signed_out"):
            cookie = unquote(st.context.cookies.get(PASS_COOKIE) or "")  # stored URL-encoded ("=" -> "%3D")
            remembered = read_pass(cookie, s.app_password, time.time())
            if remembered:  # a reload or a link: the browser still holds a valid pass
                st.session_state["pw_ok"] = True
                st.session_state["pw_email"] = remembered
        if st.session_state.get("pw_ok"):
            if token := st.session_state.pop("pass_to_save", None):
                _set_cookie(token, PASS_DAYS * 86400)
            return
        if st.session_state.get("signed_out"):
            _set_cookie("", 0)  # forget this browser
        mid = _frame("Title Agent · team sign-in")
        with mid, st.form("signin"):
            email = st.text_input("Your work email")
            pw = st.text_input("Team password", type="password")
            if st.form_submit_button("Sign In", type="primary", width="stretch"):
                if password_ok(pw, s.app_password) and "@" in email:
                    st.session_state["pw_ok"] = True
                    st.session_state["pw_email"] = email.strip().lower()
                    st.session_state.pop("signed_out", None)
                    st.session_state["pass_to_save"] = make_pass(st.session_state["pw_email"], s.app_password,
                                                                 time.time())
                    st.rerun()
                st.error("Wrong password, or the email is missing.")
        st.stop()

    mid = _frame("Title Agent")
    with mid:
        st.warning("This app is locked until a sign-in is set up. In Streamlit: App → Settings → Secrets, add "
                   "APP_PASSWORD (quick) or the Google sign-in [auth] section (see the README).")
    st.stop()


def sign_out_button() -> None:
    s = get_secrets()
    if s.google_login and st.user.is_logged_in:
        st.button("Sign Out", on_click=st.logout, icon=":material/logout:", width="stretch")
    elif s.app_password and st.session_state.get("pw_ok"):
        if st.button("Sign Out", icon=":material/logout:", width="stretch"):
            st.session_state.pop("pw_ok", None)
            st.session_state.pop("pw_email", None)
            st.session_state["signed_out"] = True  # the sign-in screen clears the browser's pass
            st.rerun()


def _set_cookie(value: str, max_age: int) -> None:
    """Writes (or, with max_age 0, deletes) the remembered sign-in in the browser. Components run in a same-origin
    frame, so the cookie lands on the app's own page and comes back in st.context.cookies on the next visit."""
    components.html(
        "<script>const w = window.parent;"
        f"w.document.cookie = {json.dumps(PASS_COOKIE)} + '=' + encodeURIComponent({json.dumps(value)})"
        f" + '; path=/; max-age={int(max_age)}; SameSite=Lax'"
        " + (w.location.protocol === 'https:' ? '; Secure' : '');"
        "</script>",
        height=0,
    )
