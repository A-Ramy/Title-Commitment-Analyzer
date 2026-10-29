"""Opens the app's data store: Firestore + Firebase Storage (titleagent/firestore_store.py). Used by the engine and the
daily email. Local development and tests use the Firebase emulators (scripts/firestore_emulator.sh, firebase.json)."""

from __future__ import annotations

import os

from titleagent.config import DATA_DIR, Secrets


def open_store(secrets: Secrets):
    from titleagent.firestore_store import FirestoreStore, GcsBlobs, LocalBlobs

    if not secrets.firebase_project:
        raise RuntimeError("FIREBASE_PROJECT_ID is not set.")
    credentials = None
    if secrets.firebase_credentials:  # GitHub Actions; on Cloud Run the engine's own Google identity is used
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_info(secrets.firebase_credentials)
    bucket = secrets.firebase_bucket or f"{secrets.firebase_project}.firebasestorage.app"
    blobs = None
    if os.environ.get("STORAGE_EMULATOR_HOST"):  # local development: the Firebase Storage emulator
        from google.auth.credentials import AnonymousCredentials

        blobs = GcsBlobs(bucket, AnonymousCredentials(), secrets.firebase_project)
    elif os.environ.get("FIRESTORE_EMULATOR_HOST"):  # local development without the Storage emulator
        blobs = LocalBlobs(DATA_DIR / "blobs")
    return FirestoreStore(project=secrets.firebase_project, bucket=bucket, credentials=credentials, blobs=blobs)
