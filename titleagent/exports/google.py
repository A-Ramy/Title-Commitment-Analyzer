"""Google Sheets and Google Docs: the Excel / Word export uploaded into the team's Shared Drive folder and converted
by Drive, so the Google versions keep the same layout. Written by a service account that is a Content Manager on
that Shared Drive (service accounts have no Drive storage of their own)."""

from __future__ import annotations

import io

SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
SHEET = "application/vnd.google-apps.spreadsheet"
DOC = "application/vnd.google-apps.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class GoogleExportError(RuntimeError):
    pass


def _drive(service_account: dict):
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_info(service_account, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload(service_account: dict, folder_id: str, name: str, data: bytes, kind: str) -> str:
    """Creates the Google file and returns its link. kind: 'sheet' or 'doc'."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaIoBaseUpload

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
    return f["webViewLink"]
