"""Shared fixtures. Storage tests run against the local Firestore emulator (scripts/firestore_emulator.sh, then
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 uv run pytest); without it they are skipped."""

import os
import uuid

import pytest


def firestore_store(project: str | None = None):
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        pytest.skip("Firestore emulator not running (scripts/firestore_emulator.sh)")
    from google.cloud import firestore

    from titleagent.firestore_store import FirestoreStore, MemoryBlobs

    # a fresh project per test keeps the emulator's data apart
    client = firestore.Client(project=project or f"test-{uuid.uuid4().hex[:10]}")
    return FirestoreStore(client=client, blobs=MemoryBlobs())


@pytest.fixture
def store():
    return firestore_store()
