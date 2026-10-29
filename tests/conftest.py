"""Shared fixtures. The Firestore store runs against the local emulator when FIRESTORE_EMULATOR_HOST is set
(scripts/firestore_emulator.sh); without it those tests are skipped."""

import os
import uuid

import pytest

from titleagent.storage import Store


@pytest.fixture(params=["sql", "firestore"])
def any_store(request, tmp_path):
    """The same tests run on the SQL store and the Firestore store."""
    if request.param == "sql":
        return Store(f"sqlite:///{tmp_path / 't.db'}")
    return firestore_store()


def firestore_store(project: str | None = None):
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        pytest.skip("Firestore emulator not running (scripts/firestore_emulator.sh)")
    from google.cloud import firestore

    from titleagent.firestore_store import FirestoreStore, MemoryBlobs

    # a fresh project per test keeps the emulator's data apart
    client = firestore.Client(project=project or f"test-{uuid.uuid4().hex[:10]}")
    return FirestoreStore(client=client, blobs=MemoryBlobs())
