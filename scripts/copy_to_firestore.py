"""One-time copy of the Title Agent's data from the SQL database (Postgres) into Firebase (v2).

Copies settings, lessons, documents (the PDFs go to Storage), deals, every review run, each deal's live list,
feedback, training examples and scores, keeping every id, so links and history stay the same. Safe to run again:
records are overwritten by id, nothing is deleted. Ends by comparing the counts on both sides.

Runs from GitHub (Actions → Copy to Firestore → Run workflow) with the repository's secrets: DATABASE_URL,
FIREBASE_PROJECT_ID, FIREBASE_SERVICE_ACCOUNT_JSON (and FIREBASE_STORAGE_BUCKET if not the default). The log shows
counts only, never deal details.

    uv run python scripts/copy_to_firestore.py [--dry-run]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from titleagent import storage as sql  # noqa: E402
from titleagent.models import ActionItem  # noqa: E402

TABLES = ("settings", "lessons", "documents", "deals", "runs", "items", "feedback", "examples", "scores")


def sql_counts(src: sql.Store) -> dict[str, int]:
    tables = {"settings": sql.settings_t, "lessons": sql.lessons_t, "documents": sql.documents_t,
              "deals": sql.deals_t, "runs": sql.runs_t, "items": sql.items_t, "feedback": sql.feedback_t,
              "examples": sql.examples_t, "scores": sql.scores_t}
    with src.engine.connect() as c:
        return {k: c.execute(select(func.count()).select_from(t)).scalar() for k, t in tables.items()}


def firestore_counts(dst) -> dict[str, int]:
    db = dst.db
    deals = [s.id for s in db.collection("deals").stream()]
    return {
        "settings": len(list(db.collection("settings").stream())),
        "lessons": len(list(db.collection("lessons").stream())),
        "documents": len(list(db.collection("documents").stream())),
        "deals": len(deals),
        "runs": sum(len(list(db.collection(f"deals/{d}/runs").stream())) for d in deals),
        "items": sum(len(list(db.collection(f"deals/{d}/items").stream())) for d in deals),
        "feedback": len(list(db.collection("feedback").stream())),
        "examples": len(list(db.collection("examples").stream())),
        "scores": len(list(db.collection("scores").stream())),
    }


def copy(src: sql.Store, dst, log=print) -> dict[str, int]:
    """Copies everything; returns the highest id per kind (the counters continue above them)."""
    rows = lambda table: [dict(r._mapping) for r in c.execute(select(table).order_by(*table.primary_key))]  # noqa: E731
    top: dict[str, int] = {}
    with src.engine.connect() as c:
        for r in rows(sql.settings_t):
            dst.db.document(f"settings/{r['key']}").set({"value": r["value"], "updated_at": r["updated_at"],
                                                         "updated_by": r["updated_by"]})
        for r in rows(sql.lessons_t):
            dst.add_lesson(r["text"], source=r["source"], by=r["created_by"], approved_by=r["approved_by"],
                           lesson_id=r["id"], created_at=r["created_at"], active=r["active"])
            top["lessons"] = r["id"]
        for r in rows(sql.documents_t):
            dst.save_document(r["data"], r["filename"], r["kind"], by=r["uploaded_by"], deal_id=r["deal_id"],
                              doc_id=r["id"], uploaded_at=r["uploaded_at"])
            top["documents"] = r["id"]
        log(f"documents: {top.get('documents', 0)}")
        deal_rows = {r["id"]: r for r in rows(sql.deals_t)}
        deal_ids = []
        for r in deal_rows.values():
            fields = {k: r[k] for k in ("address", "state", "county", "deal_type", "closing_date", "tc",
                                        "title_company", "commitment_number", "notes", "status")}
            dst.create_deal(by=r["created_by"], deal_id=r["id"], created_at=r["created_at"],
                            updated_at=r["updated_at"], **fields)
            deal_ids.append(r["id"])
            top["deals"] = r["id"]
        for r in rows(sql.runs_t):
            dst.save_run(r["deal_id"], r["analysis"], r["commitment_doc_id"], r["contract_doc_id"],
                         r["updated_commitment"], by=r["created_by"], run_id=r["id"], created_at=r["created_at"],
                         replace_items=False)
            top["runs"] = r["id"]
        for deal_id in deal_ids:  # each deal's live list, statuses and notes as the TCs left them
            items = c.execute(select(sql.items_t).where(sql.items_t.c.deal_id == deal_id)
                              .order_by(sql.items_t.c.position)).all()
            dst.replace_items(deal_id, [ActionItem.model_validate(i.data) for i in items])
            for i in items:  # keep who last touched each item and when
                dst.db.document(f"deals/{deal_id}/items/{_item_id(i.key)}").update(
                    {"position": i.position, "updated_at": i.updated_at, "updated_by": i.updated_by})
            dst.db.document(f"deals/{deal_id}").update({"updated_at": deal_rows[deal_id]["updated_at"]})
        log(f"deals: {len(deal_ids)}")
        for r in rows(sql.feedback_t):
            dst.add_feedback(r["kind"], r["text"], by=r["created_by"], deal_id=r["deal_id"],
                             item_key=r["item_key"], detail=r["detail"], feedback_id=r["id"],
                             created_at=r["created_at"], status=r["status"], lesson_id=r["lesson_id"])
            top["feedback"] = r["id"]
        for r in rows(sql.examples_t):
            dst.add_example(r["name"], r["document_id"], r["expert_items"], deal_type=r["deal_type"],
                            by=r["created_by"], example_id=r["id"], created_at=r["created_at"])
            top["examples"] = r["id"]
        for r in rows(sql.scores_t):  # a fixed id per score, so a second run overwrites instead of doubling
            dst.db.document(f"scores/sql-{r['id']}").set({k: r[k] for k in ("example_id", "run_at", "recall",
                                                                          "matched", "total", "lessons")})
    for kind, n in top.items():
        dst._ensure_counter(kind, n)
    return top


def _item_id(key: str) -> str:
    from titleagent.firestore_store import _item_id as item_id

    return item_id(key)


def main() -> int:
    from titleagent.config import load_secrets

    secrets = load_secrets()
    if not secrets.database_url or not secrets.firebase_project:
        print("Set DATABASE_URL and FIREBASE_PROJECT_ID (and FIREBASE_SERVICE_ACCOUNT_JSON) first.")
        return 1
    src = sql.Store(secrets.database_url)
    before = sql_counts(src)
    print("SQL database:", before)
    if "--dry-run" in sys.argv:
        return 0
    dst = sql.open_store(secrets)  # Firestore, because FIREBASE_PROJECT_ID is set
    copy(src, dst)
    after = firestore_counts(dst)
    print("Firestore:   ", after)
    wrong = {k: (before[k], after[k]) for k in TABLES if before[k] != after[k]}
    if wrong:
        print("Counts differ (SQL, Firestore):", wrong)
        return 1
    print("Every record copied; counts match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
