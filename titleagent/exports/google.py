"""The team's Google Drive folder: every export is saved there, in a folder for its type (FOLDERS), with the date and
time in its name. PDF / Word / Excel / CSV go as they are (and still download to the person's computer); Google
Sheets and Docs are the Excel / Word export converted by Drive, so they keep the same layout. Two ways in, the
first one set wins:

1. The Apps Script web app (google_export.gs), deployed by a team member: writes as that person. Easy setup: no
   Google Cloud project, no service account, works with any folder that person can add files to.
2. A service account that is a Content Manager on a Shared Drive (it has no Drive storage of its own)."""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

from titleagent.config import Secrets

SCRIPT = (Path(__file__).with_name("google_export.gs")).read_text(encoding="utf-8")

SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
SHEET = "application/vnd.google-apps.spreadsheet"
DOC = "application/vnd.google-apps.document"
FOLDER = "application/vnd.google-apps.folder"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SCRIPT_VERSION = 2  # google_export.gs's VERSION: older scripts can't make the folders per type

# kind → (the folder inside the team's folder, the file's type, the Google type it becomes or None to keep it as is)
FOLDERS = {"pdf": ("PDF", "application/pdf", None), "docx": ("Word", DOCX, None), "xlsx": ("Excel", XLSX, None),
           "csv": ("CSV", "text/csv", None), "sheet": ("Google Sheets", XLSX, SHEET), "doc": ("Google Docs", DOCX, DOC)}
OLD_SCRIPT = ("The Google export script is the old version. Settings → Google Exports → Show The Setup Steps → Copy "
              "The Script, paste it over the old one and Save, then Deploy → Manage deployments → edit → Version: "
              "New version → Deploy.")


class GoogleExportError(RuntimeError):
    pass


def folder_id_from(text: str) -> str:
    """The folder ID from a pasted Drive link (…/folders/<id>?usp=…, or ?id=<id>) or the bare ID."""
    text = text.strip()
    m = re.search(r"/folders/([\w-]+)", text) or re.search(r"[?&]id=([\w-]+)", text)
    return m.group(1) if m else text


def check_folder(service_account: dict, folder_id: str) -> tuple[bool, str]:
    """(ok, message): can the app create files in this folder? Reads only; creates nothing."""
    from googleapiclient.errors import HttpError

    email = service_account.get("client_email", "the service account")
    folder_id = folder_id_from(folder_id)
    if not folder_id:
        return False, "Paste the Shared Drive folder's link in Settings first."
    try:
        f = _drive(service_account).files().get(
            fileId=folder_id, fields="name, mimeType, driveId, capabilities(canAddChildren)", supportsAllDrives=True,
        ).execute()
    except HttpError as exc:
        status = getattr(exc, "status_code", None) or getattr(getattr(exc, "resp", None), "status", None)
        if "has not been used" in str(exc) or "is disabled" in str(exc):
            return False, "The Google Drive API is off for this service account's project. Enable it, then retry."
        if str(status) in ("403", "404"):
            return False, (f"The app can't see that folder. Add {email} to the Shared Drive as Content Manager "
                           "(Shared Drive → Manage members), then test again.")
        return False, f"Google Drive returned an error ({status})."
    except Exception:  # a bad or incomplete key, or no network; never echo the key
        return False, "The app couldn't sign in to Google with the service account key. Check the key in the secrets."
    if f.get("mimeType") != "application/vnd.google-apps.folder":
        return False, "That link is a file, not a folder. Open the folder and copy its link."
    if not f.get("driveId"):
        return False, ("That folder is in someone's My Drive. Use a folder inside a Shared Drive: service accounts "
                       "have no storage of their own.")
    if not (f.get("capabilities") or {}).get("canAddChildren"):
        return False, f"{email} can see “{f.get('name')}” but can't add files. Make it a Content Manager."
    return True, f"Connected: exports go to “{f.get('name')}”, a folder for each type."


def _drive(service_account: dict):
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_info(service_account, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _subfolder(drive, parent: str, name: str) -> str:
    """The folder for this type inside the team's folder, made the first time."""
    q = f"'{parent}' in parents and name = '{name}' and mimeType = '{FOLDER}' and trashed = false"
    found = drive.files().list(q=q, corpora="allDrives", includeItemsFromAllDrives=True, supportsAllDrives=True,
                               fields="files(id)").execute().get("files", [])
    if found:
        return found[0]["id"]
    return drive.files().create(body={"name": name, "mimeType": FOLDER, "parents": [parent]}, fields="id",
                                supportsAllDrives=True).execute()["id"]


def upload(service_account: dict, folder_id: str, name: str, data: bytes, kind: str) -> str:
    """Saves the file in its type's folder and returns its link. kind: a key of FOLDERS."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaIoBaseUpload

    folder_id = folder_id_from(folder_id)
    if not folder_id:
        raise GoogleExportError("Set the Google Drive folder in Settings first.")
    sub, source, target = FOLDERS[kind]
    try:
        drive = _drive(service_account)
        body = {"name": name, "parents": [_subfolder(drive, folder_id, sub)]}
        if target:
            body["mimeType"] = target
        f = drive.files().create(
            body=body,
            media_body=MediaIoBaseUpload(io.BytesIO(data), mimetype=source, resumable=False),
            fields="id, webViewLink",
            supportsAllDrives=True,
        ).execute()
    except HttpError as exc:
        status = getattr(exc, "status_code", None) or getattr(getattr(exc, "resp", None), "status", None)
        if str(status) in ("403", "404"):
            email = service_account.get("client_email", "the service account")
            raise GoogleExportError(f"The app can't write to that folder. Add {email} to the Shared Drive as "
                                    "Content Manager, and check the folder ID in Settings.") from exc
        raise GoogleExportError(f"Google Drive returned an error ({status}). Try again.") from exc
    except Exception as exc:
        raise GoogleExportError("The app couldn't sign in to Google with the service account key. Check the key "
                                "in the secrets.") from exc
    return f["webViewLink"]


# ---- the Apps Script web app
def _script_error(error: str) -> str:
    if error == "wrong key":
        return "The export key doesn't match. Copy GOOGLE_EXPORT_KEY again from the script's setup log."
    if error == "not a folder":
        return "That link is a file, not a folder. Open the folder and copy its link."
    if error == "unknown kind":
        return OLD_SCRIPT
    if error == "read only":
        return "The script's Google account can only view that folder. Give it edit access, or deploy as an editor."
    if "Drive is not defined" in error:
        return ("The script is missing the Drive service: in the script editor click Services (+) → Drive API → Add, "
                "then Deploy → Manage deployments → edit → New version.")
    if "is not a function" in error:
        return ("The script's Drive service is the old version: in the script editor click Drive under Services, "
                "choose version v3, then Deploy → Manage deployments → edit → New version.")
    if "not found" in error.lower():
        return "The script's Google account can't open that folder. Check the link, or share the folder with it."
    return f"Google Drive said: {error}"


def _script(secrets: Secrets, payload: dict, timeout: int = 90) -> dict:
    import requests

    try:
        r = requests.post(secrets.google_export_url, json={**payload, "key": secrets.google_export_key},
                          timeout=timeout)
        out = r.json()
    except requests.RequestException as exc:
        raise GoogleExportError("Couldn't reach the Google export script. Try again.") from exc
    except ValueError as exc:  # an HTML sign-in page: the deployment isn't open to "Anyone"
        raise GoogleExportError("The Google export script didn't answer. Check GOOGLE_EXPORT_URL is the web app URL "
                                "(ends in /exec) and the deployment's Who has access is Anyone.") from exc
    if not out.get("ok"):
        raise GoogleExportError(_script_error(str(out.get("error", ""))))
    return out


def export(secrets: Secrets, folder: str, name: str, data: bytes, kind: str, timeout: int = 90) -> str:
    """Saves the export in the team's folder, in its type's folder, and returns its link. kind: a key of FOLDERS
    ('sheet' / 'doc' become a Google Sheet / Doc)."""
    folder_id = folder_id_from(folder)
    if not folder_id:
        raise GoogleExportError("Set the Google Drive folder in Settings first.")
    if secrets.google_export_url and secrets.google_export_key:
        sub, source, target = FOLDERS[kind]
        return _script(secrets, {"action": "save", "folder": folder_id, "subfolder": sub, "name": name,
                                 "type": source, "convert": target or "", "data": base64.b64encode(data).decode()},
                       timeout)["link"]
    if secrets.google_service_account:
        return upload(secrets.google_service_account, folder_id, name, data, kind)
    raise GoogleExportError("Google exports aren't set up yet (Settings → Google Exports).")


def check(secrets: Secrets, folder: str) -> tuple[bool, str]:
    """(ok, message) for Settings → Test Google Folder. Creates nothing."""
    folder_id = folder_id_from(folder)
    if not folder_id:
        return False, "Paste the folder's link in Settings and save first."
    if secrets.google_export_url and secrets.google_export_key:
        try:
            out = _script(secrets, {"action": "ping", "folder": folder_id})
        except GoogleExportError as exc:
            return False, str(exc)
        if (out.get("version") or 0) < SCRIPT_VERSION:
            return False, f"Connected to “{out.get('folder')}”, but: {OLD_SCRIPT}"
        return True, f"Connected: exports go to “{out.get('folder')}”, a folder for each type."
    if secrets.google_service_account:
        return check_folder(secrets.google_service_account, folder_id)
    return False, "Google exports aren't set up yet."
