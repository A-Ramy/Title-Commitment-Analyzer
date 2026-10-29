"""The app's data in Firebase (Title Agent v2): Firestore for records, Cloud Storage for the PDFs and each review's
full analysis. Same methods and return shapes as storage.Store, so the app, the daily email and the tests work with
either one.

Layout (ids are the same integers as the SQL store, so links and the one-time copy keep them):
    settings/{key}                       value, updated_at, updated_by
    deals/{id}                           deal fields (closing_date as YYYY-MM-DD)
    deals/{id}/items/{hash of key}       position, data (ActionItem), updated_at, updated_by
    deals/{id}/runs/{id}                 run metadata; the analysis JSON is in Storage at runs/{id}.json
    documents/{id}                       metadata; the file is in Storage at documents/{id}/{filename}
    feedback/{id}, lessons/{id}, examples/{id}, scores/{auto}
    meta/counters                        the last id handed out per kind

Queries avoid composite indexes (equality filters only, sorting in Python): the team has tens of deals open at a time.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from typing import Protocol

from titleagent.config import DEFAULT_SETTINGS
from titleagent.models import ActionItem, Analysis
from titleagent.prompts import REVISED_SEED_LESSONS, SEED_LESSONS

BATCH = 400  # Firestore allows 500 writes per batch


class Blobs(Protocol):
    def put(self, path: str, data: bytes, content_type: str) -> None: ...
    def get(self, path: str) -> bytes: ...


class GcsBlobs:
    """The Firebase Storage bucket."""

    def __init__(self, bucket: str, credentials=None, project: str | None = None):
        from google.cloud import storage

        self.bucket = storage.Client(project=project, credentials=credentials).bucket(bucket)

    def put(self, path: str, data: bytes, content_type: str) -> None:
        self.bucket.blob(path).upload_from_string(data, content_type=content_type)

    def get(self, path: str) -> bytes:
        return self.bucket.blob(path).download_as_bytes()


class LocalBlobs:
    """Files in a local folder: development against the Firestore emulator."""

    def __init__(self, root):
        from pathlib import Path

        self.root = Path(root)

    def put(self, path: str, data: bytes, content_type: str) -> None:
        f = self.root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)

    def get(self, path: str) -> bytes:
        return (self.root / path).read_bytes()


class MemoryBlobs:
    """For tests and the emulator."""

    def __init__(self):
        self.files: dict[str, bytes] = {}

    def put(self, path: str, data: bytes, content_type: str) -> None:
        self.files[path] = data

    def get(self, path: str) -> bytes:
        return self.files[path]


def _now() -> datetime:
    return datetime.now(UTC)


def _item_id(key: str) -> str:
    return hashlib.sha1(key.encode()).hexdigest()[:20]  # item keys can hold characters Firestore ids can't


def _safe_name(filename: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", filename)[:120] or "file"


def _deal_out(d: dict) -> dict:
    if isinstance(d.get("closing_date"), str) and d["closing_date"]:
        d["closing_date"] = date.fromisoformat(d["closing_date"])
    elif not d.get("closing_date"):
        d["closing_date"] = None
    return d


def _deal_in(fields: dict) -> dict:
    out = dict(fields)
    if isinstance(out.get("closing_date"), date):
        out["closing_date"] = out["closing_date"].isoformat()
    return out


class FirestoreStore:
    def __init__(self, client=None, blobs: Blobs | None = None, project: str | None = None,
                 bucket: str | None = None, credentials=None):
        if client is None:
            from google.cloud import firestore

            client = firestore.Client(project=project, credentials=credentials)
        self.db = client
        self.blobs = blobs or GcsBlobs(bucket or f"{project}.firebasestorage.app", credentials, project)
        self._seed_lessons()

    # ---- ids
    def _next_id(self, kind: str) -> int:
        from google.cloud import firestore

        ref = self.db.document("meta/counters")

        @firestore.transactional
        def bump(tx) -> int:
            snap = ref.get(transaction=tx)
            n = int((snap.to_dict() or {}).get(kind, 0)) + 1 if snap.exists else 1
            tx.set(ref, {kind: n}, merge=True)
            return n

        return bump(self.db.transaction())

    def _ensure_counter(self, kind: str, at_least: int) -> None:
        """After a copy with fixed ids, new ids continue above them."""
        ref = self.db.document("meta/counters")
        snap = ref.get()
        if int((snap.to_dict() or {}).get(kind, 0)) < at_least:
            ref.set({kind: at_least}, merge=True)

    def _sorted(self, collection: str, field: str = "id", reverse: bool = False, **equals) -> list[dict]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        q = self.db.collection(collection)
        for k, v in equals.items():
            q = q.where(filter=FieldFilter(k, "==", v))
        return sorted((s.to_dict() for s in q.stream()), key=lambda d: d.get(field) or 0, reverse=reverse)

    def _seed_lessons(self) -> None:
        from google.cloud.firestore_v1.base_query import FieldFilter

        lessons = self.db.collection("lessons")
        for old, new in REVISED_SEED_LESSONS.items():  # owner changed a rule after the database was seeded
            for s in lessons.where(filter=FieldFilter("text", "==", old)).stream():
                if s.get("source") == "seed":
                    s.reference.update({"text": new})
        if next(iter(lessons.limit(1).stream()), None) is not None:
            return
        for t in SEED_LESSONS:
            self.add_lesson(t, source="seed", by="Title Agent", approved_by="Initial training set")

    # ---- settings
    def get_settings(self) -> dict:
        saved = {s.id: s.get("value") for s in self.db.collection("settings").stream()}
        return {**DEFAULT_SETTINGS, **saved}

    def set_setting(self, key: str, value, by: str = "") -> None:
        self.db.document(f"settings/{key}").set({"value": value, "updated_at": _now(), "updated_by": by})

    # ---- documents
    def save_document(self, data: bytes, filename: str, kind: str, by: str = "", deal_id: int | None = None,
                      doc_id: int | None = None, uploaded_at: datetime | None = None) -> int:
        doc_id = doc_id or self._next_id("documents")
        path = f"documents/{doc_id}/{_safe_name(filename)}"
        self.blobs.put(path, data, "application/pdf" if filename.lower().endswith(".pdf") else
                       "application/octet-stream")
        self.db.document(f"documents/{doc_id}").set({
            "id": doc_id, "deal_id": deal_id, "kind": kind, "filename": filename,
            "uploaded_at": uploaded_at or _now(), "uploaded_by": by, "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "path": path})
        return doc_id

    def attach_document(self, doc_id: int, deal_id: int) -> None:
        self.db.document(f"documents/{doc_id}").update({"deal_id": deal_id})

    def get_document(self, doc_id: int) -> dict | None:
        snap = self.db.document(f"documents/{doc_id}").get()
        if not snap.exists:
            return None
        d = snap.to_dict()
        return {**d, "data": self.blobs.get(d["path"])}

    def list_documents(self, deal_id: int) -> list[dict]:
        keep = ("id", "kind", "filename", "uploaded_at", "uploaded_by", "size")
        return [{k: d.get(k) for k in keep} for d in self._sorted("documents", deal_id=deal_id)]

    # ---- deals
    def create_deal(self, by: str = "", deal_id: int | None = None, created_at: datetime | None = None,
                    updated_at: datetime | None = None, **fields) -> int:
        deal_id = deal_id or self._next_id("deals")
        now = _now()
        base = {"address": "", "state": "", "county": "", "deal_type": "", "closing_date": None, "tc": "",
                "title_company": "", "commitment_number": "", "notes": "", "status": "open"}
        self.db.document(f"deals/{deal_id}").set({**base, **_deal_in(fields), "id": deal_id,
                                                   "created_at": created_at or now,
                                                   "updated_at": updated_at or now, "created_by": by})
        return deal_id

    def update_deal(self, deal_id: int, **fields) -> None:
        self.db.document(f"deals/{deal_id}").update({**_deal_in(fields), "updated_at": _now()})

    def get_deal(self, deal_id: int) -> dict | None:
        snap = self.db.document(f"deals/{deal_id}").get()
        return _deal_out(snap.to_dict()) if snap.exists else None

    def list_deals(self, status: str | None = None) -> list[dict]:
        rows = self._sorted("deals", "updated_at", reverse=True, **({"status": status} if status else {}))
        return [_deal_out(d) for d in rows]

    # ---- runs and the live list
    def save_run(self, deal_id: int, analysis: Analysis, commitment_doc_id: int, contract_doc_id: int | None,
                 updated_commitment: bool, by: str = "", run_id: int | None = None,
                 created_at: datetime | None = None, replace_items: bool = True) -> int:
        run_id = run_id or self._next_id("runs")
        payload = analysis.model_dump(mode="json") if isinstance(analysis, Analysis) else analysis
        self.blobs.put(f"runs/{run_id}.json", json.dumps(payload).encode(), "application/json")
        usage = payload.get("usage") or {}
        self.db.document(f"deals/{deal_id}/runs/{run_id}").set({
            "id": run_id, "deal_id": deal_id, "created_at": created_at or _now(), "created_by": by,
            "commitment_doc_id": commitment_doc_id, "contract_doc_id": contract_doc_id,
            "updated_commitment": updated_commitment, "cost_usd": float(usage.get("cost_usd", 0.0)),
            "analysis_path": f"runs/{run_id}.json"})
        if replace_items:
            self.replace_items(deal_id, [ActionItem.model_validate(i) for i in payload.get("items", [])], by=by)
        return run_id

    def latest_run(self, deal_id: int) -> dict | None:
        from google.cloud import firestore

        q = self.db.collection(f"deals/{deal_id}/runs").order_by("id", direction=firestore.Query.DESCENDING)
        snap = next(iter(q.limit(1).stream()), None)
        if snap is None:
            return None
        d = snap.to_dict()
        return {**d, "analysis": json.loads(self.blobs.get(d["analysis_path"]))}

    def list_runs(self, deal_id: int) -> list[dict]:
        keep = ("id", "created_at", "created_by", "updated_commitment", "cost_usd")
        rows = sorted((s.to_dict() for s in self.db.collection(f"deals/{deal_id}/runs").stream()),
                      key=lambda d: d["id"], reverse=True)
        return [{k: d.get(k) for k in keep} for d in rows]

    def replace_items(self, deal_id: int, items: list[ActionItem], by: str = "",
                      updated_at: datetime | None = None) -> None:
        col = self.db.collection(f"deals/{deal_id}/items")
        now = updated_at or _now()
        writes = [("delete", s.reference, None) for s in col.stream()]
        writes += [("set", col.document(_item_id(i.key)), {"key": i.key, "position": n,
                                                            "data": i.model_dump(mode="json"),
                                                            "updated_at": now, "updated_by": by})
                   for n, i in enumerate(items)]
        for start in range(0, len(writes), BATCH):
            batch = self.db.batch()
            for op, ref, data in writes[start:start + BATCH]:
                batch.delete(ref) if op == "delete" else batch.set(ref, data)
            batch.commit()
        self.db.document(f"deals/{deal_id}").update({"updated_at": _now()})

    def get_items(self, deal_id: int) -> list[ActionItem]:
        rows = sorted((s.to_dict() for s in self.db.collection(f"deals/{deal_id}/items").stream()),
                      key=lambda d: d["position"])
        return [ActionItem.model_validate(r["data"]) for r in rows]

    def update_item(self, deal_id: int, key: str, by: str = "", **changes) -> None:
        ref = self.db.document(f"deals/{deal_id}/items/{_item_id(key)}")
        snap = ref.get()
        if not snap.exists:
            return
        ref.update({"data": {**snap.get("data"), **changes}, "updated_at": _now(), "updated_by": by})
        self.db.document(f"deals/{deal_id}").update({"updated_at": _now()})

    def add_item(self, deal_id: int, item: ActionItem, by: str = "") -> None:
        col = self.db.collection(f"deals/{deal_id}/items")
        pos = max((s.get("position") for s in col.stream()), default=0)
        col.document(_item_id(item.key)).set({"key": item.key, "position": pos + 1,
                                               "data": item.model_dump(mode="json"), "updated_at": _now(),
                                               "updated_by": by})

    def open_items_by_deal(self) -> dict[int, list[ActionItem]]:
        """Every open deal's list (daily email, Deals page)."""
        out: dict[int, list[ActionItem]] = {}
        for d in self._sorted("deals", status="open"):
            items = self.get_items(d["id"])
            if items:
                out[d["id"]] = items
        return out

    # ---- feedback and lessons
    def add_feedback(self, kind: str, text: str, by: str = "", deal_id: int | None = None,
                     item_key: str | None = None, detail: dict | None = None, feedback_id: int | None = None,
                     created_at: datetime | None = None, status: str = "pending",
                     lesson_id: int | None = None) -> int:
        feedback_id = feedback_id or self._next_id("feedback")
        self.db.document(f"feedback/{feedback_id}").set({
            "id": feedback_id, "created_at": created_at or _now(), "created_by": by, "deal_id": deal_id,
            "item_key": item_key, "kind": kind, "text": text, "detail": detail or {}, "status": status,
            "lesson_id": lesson_id})
        return feedback_id

    def list_feedback(self, status: str | None = "pending") -> list[dict]:
        return self._sorted("feedback", reverse=True, **({"status": status} if status else {}))

    def resolve_feedback(self, feedback_id: int, approve: bool, lesson_text: str = "", by: str = "") -> int | None:
        lesson_id = self.add_lesson(lesson_text, source="feedback", by=by, approved_by=by) if approve else None
        self.db.document(f"feedback/{feedback_id}").update({"status": "approved" if approve else "rejected",
                                                            "lesson_id": lesson_id})
        return lesson_id

    def add_lesson(self, text: str, source: str = "manual", by: str = "", approved_by: str = "",
                   lesson_id: int | None = None, created_at: datetime | None = None, active: bool = True) -> int:
        lesson_id = lesson_id or self._next_id("lessons")
        self.db.document(f"lessons/{lesson_id}").set({
            "id": lesson_id, "created_at": created_at or _now(), "created_by": by, "text": text.strip(),
            "source": source, "active": active, "approved_by": approved_by or by})
        return lesson_id

    def list_lessons(self, active_only: bool = False) -> list[dict]:
        return self._sorted("lessons", **({"active": True} if active_only else {}))

    def active_lessons(self) -> list[str]:
        """In id order, so the system prompt (and its cache) only changes when a lesson changes."""
        return [r["text"] for r in self.list_lessons(active_only=True)]

    def set_lesson(self, lesson_id: int, **fields) -> None:
        self.db.document(f"lessons/{lesson_id}").update(fields)

    # ---- training examples and the scorecard
    def add_example(self, name: str, document_id: int, expert_items: list[str], deal_type: str = "",
                    by: str = "", example_id: int | None = None, created_at: datetime | None = None) -> int:
        example_id = example_id or self._next_id("examples")
        self.db.document(f"examples/{example_id}").set({
            "id": example_id, "created_at": created_at or _now(), "created_by": by, "name": name,
            "document_id": document_id, "expert_items": expert_items, "deal_type": deal_type})
        return example_id

    def list_examples(self) -> list[dict]:
        return self._sorted("examples")

    def add_score(self, example_id: int, recall: float, matched: int, total: int, lessons: int,
                  run_at: datetime | None = None) -> None:
        self.db.collection("scores").add({"example_id": example_id, "run_at": run_at or _now(), "recall": recall,
                                          "matched": matched, "total": total, "lessons": lessons})

    def list_scores(self) -> list[dict]:
        return sorted((s.to_dict() for s in self.db.collection("scores").stream()), key=lambda d: d["run_at"])
