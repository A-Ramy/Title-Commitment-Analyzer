"""Google Sheets and Google Docs: the Excel / Word export uploaded into the team's Shared Drive folder and converted
by Drive, so the Google versions keep the same layout. Written by a service account that is a Content Manager on
that Shared Drive (service accounts have no Drive storage of their own)."""

from __future__ import annotations

import io
import re

SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
SHEET = "application/vnd.google-apps.spreadsheet"
DOC = "application/vnd.google-apps.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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
    return True, f"Connected: exports go to “{f.get('name')}”."


def _drive(service_account: dict):
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_info(service_account, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload(service_account: dict, folder_id: str, name: str, data: bytes, kind: str) -> str:
    """Creates the Google file and returns its link. kind: 'sheet' or 'doc'."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaIoBaseUpload

    folder_id = folder_id_from(folder_id)
    if not folder_id:
        raise GoogleExportError("Set the Google Drive folder in Settings first.")
    target, source = (SHEET, XLSX) if kind == "sheet" else (DOC, DOCX)
    try:
        f = _drive(service_account).files().create(
            body={"name": name, "mimeType": target, "parents": [folder_id]},
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
