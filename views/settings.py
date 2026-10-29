"""Settings: admins, TCs, the daily email, due-date offsets and the Google Drive folder. Admins only."""

from __future__ import annotations

import streamlit as st

from titleagent.config import DEFAULT_SETTINGS
from titleagent.emailer import LAST_RUN, run_status
from titleagent.exports import google
from ui import html as h
from ui.state import get_secrets, get_settings, get_store, is_admin, who

store = get_store()
settings = get_settings()
secrets = get_secrets()
admin = is_admin()

st.title("Settings")
if not admin:
    h.box("Only admins can change settings.", "warn")


def lines(value: list[str]) -> str:
    return "\n".join(value or [])


def parse(text: str) -> list[str]:
    return [x.strip() for x in text.replace(",", "\n").splitlines() if x.strip()]


with st.form("settings"):
    h.heading("People", "1")
    c1, c2 = st.columns(2)
    admins = c1.text_area("Admins (emails, one per line)", lines(settings["admins"]),
                          help="Approve lessons and change settings. Empty = everyone (first-time setup).")
    tcs = c2.text_area("TCs (names or emails, one per line)", lines(settings["tcs"]),
                       help="Picked when a deal is set up; the TC owns every item on the deal.")
    h.heading("Daily Email", "2", "Each morning: every open deal's blockers and items due in the next 3 days")
    c3, c4 = st.columns(2)
    recipients = c3.text_area("Send to (emails, one per line)", lines(settings["email_recipients"]))
    sender = c4.text_input("Send from", settings["email_from"])
    h.heading("Due Dates", "3", "Days before closing each kind of item is due (weekends move back to Friday)")
    offsets = dict(settings["due_offsets"])
    cols = st.columns(len(offsets))
    labels = {"payoff": "Payoff letters", "curative": "Court / curative", "documents": "Documents",
              "bring_down": "Bring-down", "closing": "At closing"}
    for col, k in zip(cols, list(offsets), strict=True):
        offsets[k] = col.number_input(labels.get(k, k), min_value=0, max_value=60, value=int(offsets[k]), step=1)
    h.heading("Google Exports", "4", "Google Sheets and Docs exports are saved in this Google Drive folder")
    folder = st.text_input("Google Drive folder (paste its link)", settings["google_folder_id"],
                           help="Open the folder in Google Drive and copy the address bar, or paste just the ID.")
    saved = st.form_submit_button("Save Settings", type="primary", disabled=not admin)

if saved:
    for key, value in (("admins", parse(admins)), ("tcs", parse(tcs)), ("email_recipients", parse(recipients)),
                       ("email_from", sender.strip() or DEFAULT_SETTINGS["email_from"]), ("due_offsets", offsets),
                       ("google_folder_id", google.folder_id_from(folder))):
        store.set_setting(key, value, by=who())
    st.success("Saved.")
    st.rerun()

script_mode = bool(secrets.google_export_url and secrets.google_export_key)
sa_email = (secrets.google_service_account or {}).get("client_email", "")
if secrets.has_google:
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    c1.caption("Exports are saved by the Google export script, as the person who deployed it." if script_mode else
               f"Service account to add to the Shared Drive as Content Manager: `{sa_email}`")
    if c2.button("Test Google Folder", icon=":material/folder_shared:", width="stretch"):
        with st.spinner("Checking the folder…"):
            ok, msg = google.check(secrets, settings["google_folder_id"])
        (st.success if ok else st.error)(msg)
if not script_mode:
    with st.expander("Set up Google exports (about 5 minutes, no Google Cloud needed)",
                     expanded=not secrets.has_google):
        st.markdown("""
Do this signed in to Google as someone who can **add files** to the folder (files are saved as that person).

1. Go to **script.google.com** → **New project**. Delete what's in the editor, paste the script below (copy button
   at its top right) and click **Save**.
2. On the left, **Services (+)** → **Drive API** → **Add**.
3. Pick **setup** in the function menu at the top → **Run** → allow access. The log at the bottom shows
   `GOOGLE_EXPORT_KEY = "..."`.
4. **Deploy → New deployment** → type **Web app** → Execute as **Me** → Who has access **Anyone** → **Deploy** →
   copy the **Web app URL**.
5. In Streamlit: App → **Settings → Secrets**, add the two lines and save:
   `GOOGLE_EXPORT_URL = "the web app URL"` and the `GOOGLE_EXPORT_KEY` line from step 3.
6. Back here: paste the folder's link above, **Save Settings**, then **Test Google Folder**.

Only the app can use the script: every request must carry the key. If step 4 has no **Anyone** option, a Google
Workspace admin has turned it off; ask them to allow it.
""")
        st.code(google.SCRIPT, language="javascript")

h.heading("Connections", "5", "Set in the app's secrets, never here")
email_value, email_sub, email_cls = run_status(settings.get(LAST_RUN))
h.tiles([
    ("AI (Anthropic)", "Connected" if secrets.has_ai else "Not set", "ANTHROPIC_API_KEY",
     "up" if secrets.has_ai else "down"),
    ("Database", "Firestore" if secrets.firebase_project else "Postgres" if secrets.database_url else "Local file",
     "FIREBASE_PROJECT_ID" if secrets.firebase_project else "DATABASE_URL",
     "up" if secrets.has_data_store else "muted"),
    ("Google", "Set Up" if secrets.has_google else "Not set",
     "export script" if script_mode else h.esc(sa_email) if secrets.has_google else "for Sheets / Docs exports",
     "up" if secrets.has_google else "muted"),
    ("Daily Email", email_value, email_sub, email_cls),
])
