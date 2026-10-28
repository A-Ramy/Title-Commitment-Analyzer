"""The app's database: deals, their documents (kept forever, owner 2026-10-24), every review run, the live action
list, feedback, lessons and training examples.

DATABASE_URL selects the database (Postgres in the cloud); unset = SQLite in .data/app.db. Uploaded PDFs are stored
in the database itself for now; move them to object storage when the database grows past its plan.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)

from titleagent.config import DATA_DIR, DEFAULT_SETTINGS
from titleagent.models import ActionItem, Analysis
from titleagent.prompts import REVISED_SEED_LESSONS, SEED_LESSONS

metadata = MetaData()

settings_t = Table(
    "settings", metadata,
    Column("key", String(100), primary_key=True),
    Column("value", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("updated_by", String(200), nullable=False, default=""),
)

deals_t = Table(
    "deals", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("created_by", String(200), nullable=False, default=""),
    Column("address", String(300), nullable=False, default=""),
    Column("state", String(10), nullable=False, default=""),
    Column("county", String(100), nullable=False, default=""),
    Column("deal_type", String(60), nullable=False, default=""),
    Column("closing_date", Date, nullable=True),
    Column("tc", String(200), nullable=False, default=""),
    Column("title_company", String(300), nullable=False, default=""),
    Column("commitment_number", String(100), nullable=False, default=""),
    Column("notes", Text, nullable=False, default=""),
    Column("status", String(20), nullable=False, default="open"),  # open | closed | cancelled
)

documents_t = Table(
    "documents", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("deal_id", Integer, ForeignKey("deals.id"), nullable=True, index=True),
    Column("kind", String(20), nullable=False),  # commitment | contract | training
    Column("filename", String(300), nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
    Column("uploaded_by", String(200), nullable=False, default=""),
    Column("size", Integer, nullable=False),
    Column("sha256", String(64), nullable=False, index=True),
    Column("data", LargeBinary, nullable=False),
)

runs_t = Table(
    "runs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("deal_id", Integer, ForeignKey("deals.id"), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("created_by", String(200), nullable=False, default=""),
    Column("commitment_doc_id", Integer, nullable=False),
    Column("contract_doc_id", Integer, nullable=True),
    Column("updated_commitment", Boolean, nullable=False, default=False),
    Column("analysis", JSON, nullable=False),  # Analysis as JSON (structure, items as produced, coverage, usage)
    Column("cost_usd", Float, nullable=False, default=0.0),
)

items_t = Table(  # the live list a TC works: one row per item per deal
    "items", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("deal_id", Integer, ForeignKey("deals.id"), nullable=False, index=True),
    Column("key", String(80), nullable=False),
    Column("position", Integer, nullable=False, default=0),
    Column("data", JSON, nullable=False),  # ActionItem
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("updated_by", String(200), nullable=False, default=""),
)

feedback_t = Table(
    "feedback", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("created_by", String(200), nullable=False, default=""),
    Column("deal_id", Integer, nullable=True),
    Column("item_key", String(80), nullable=True),
    Column("kind", String(20), nullable=False),  # missing | not_needed | wrong | training
    Column("text", Text, nullable=False),
    Column("detail", JSON, nullable=False, default=dict),  # where, why, priority, category, suggested lesson
    Column("status", String(20), nullable=False, default="pending"),  # pending | approved | rejected
    Column("lesson_id", Integer, nullable=True),
)

lessons_t = Table(
    "lessons", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("created_by", String(200), nullable=False, default=""),
    Column("text", Text, nullable=False),
    Column("source", String(40), nullable=False, default=""),  # seed | training | feedback | manual
    Column("active", Boolean, nullable=False, default=True),
    Column("approved_by", String(200), nullable=False, default=""),
)

examples_t = Table(
    "examples", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("created_by", String(200), nullable=False, default=""),
    Column("name", String(200), nullable=False),
    Column("document_id", Integer, nullable=False),
    Column("expert_items", JSON, nullable=False),  # list[str]
    Column("deal_type", String(60), nullable=False, default=""),
)

scores_t = Table(
    "scores", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("example_id", Integer, ForeignKey("examples.id"), nullable=False, index=True),
    Column("run_at", DateTime(timezone=True), nullable=False),
    Column("recall", Float, nullable=False),
    Column("matched", Integer, nullable=False),
    Column("total", Integer, nullable=False),
    Column("lessons", Integer, nullable=False),
)


def normalize_url(url: str | None) -> str:
    if not url:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{DATA_DIR / 'app.db'}"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _now() -> datetime:
    return datetime.now(UTC)


class Store:
    def __init__(self, url: str | None = None):
        self.engine = create_engine(normalize_url(url), pool_pre_ping=True)
        metadata.create_all(self.engine)
        self._seed_lessons()

    def _seed_lessons(self) -> None:
        with self.engine.begin() as c:
            for old, new in REVISED_SEED_LESSONS.items():  # owner changed a rule after the database was seeded
                c.execute(update(lessons_t).where(lessons_t.c.source == "seed", lessons_t.c.text == old)
                          .values(text=new))
            if c.execute(select(func.count()).select_from(lessons_t)).scalar():
                return
            now = _now()
            c.execute(insert(lessons_t), [{"created_at": now, "created_by": "Title Agent", "text": t,
                                           "source": "seed", "active": True, "approved_by": "Initial training set"}
                                          for t in SEED_LESSONS])

    # ---- settings
    def get_settings(self) -> dict:
        with self.engine.connect() as c:
            saved = {r.key: r.value for r in c.execute(select(settings_t))}
        return {**DEFAULT_SETTINGS, **saved}

    def set_setting(self, key: str, value, by: str = "") -> None:
        with self.engine.begin() as c:
            exists = c.execute(select(settings_t.c.key).where(settings_t.c.key == key)).first()
            values = {"value": value, "updated_at": _now(), "updated_by": by}
            if exists:
                c.execute(update(settings_t).where(settings_t.c.key == key).values(**values))
            else:
                c.execute(insert(settings_t).values(key=key, **values))

    # ---- documents
    def save_document(self, data: bytes, filename: str, kind: str, by: str = "", deal_id: int | None = None) -> int:
        with self.engine.begin() as c:
            res = c.execute(insert(documents_t).values(
                deal_id=deal_id, kind=kind, filename=filename, uploaded_at=_now(), uploaded_by=by, size=len(data),
                sha256=hashlib.sha256(data).hexdigest(), data=data))
            return int(res.inserted_primary_key[0])

    def attach_document(self, doc_id: int, deal_id: int) -> None:
        with self.engine.begin() as c:
            c.execute(update(documents_t).where(documents_t.c.id == doc_id).values(deal_id=deal_id))

    def get_document(self, doc_id: int) -> dict | None:
        with self.engine.connect() as c:
            row = c.execute(select(documents_t).where(documents_t.c.id == doc_id)).first()
        return dict(row._mapping) if row else None

    def list_documents(self, deal_id: int) -> list[dict]:
        cols = [documents_t.c[k] for k in ("id", "kind", "filename", "uploaded_at", "uploaded_by", "size")]
        with self.engine.connect() as c:
            rows = c.execute(select(*cols).where(documents_t.c.deal_id == deal_id).order_by(documents_t.c.id))
            return [dict(r._mapping) for r in rows]

    # ---- deals
    def create_deal(self, by: str = "", **fields) -> int:
        now = _now()
        with self.engine.begin() as c:
            res = c.execute(insert(deals_t).values(created_at=now, updated_at=now, created_by=by, **fields))
            return int(res.inserted_primary_key[0])

    def update_deal(self, deal_id: int, **fields) -> None:
        with self.engine.begin() as c:
            c.execute(update(deals_t).where(deals_t.c.id == deal_id).values(updated_at=_now(), **fields))

    def get_deal(self, deal_id: int) -> dict | None:
        with self.engine.connect() as c:
            row = c.execute(select(deals_t).where(deals_t.c.id == deal_id)).first()
        return dict(row._mapping) if row else None

    def list_deals(self, status: str | None = None) -> list[dict]:
        q = select(deals_t).order_by(deals_t.c.updated_at.desc())
        if status:
            q = q.where(deals_t.c.status == status)
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(q)]

    # ---- runs and the live list
    def save_run(self, deal_id: int, analysis: Analysis, commitment_doc_id: int, contract_doc_id: int | None,
                 updated_commitment: bool, by: str = "") -> int:
        with self.engine.begin() as c:
            res = c.execute(insert(runs_t).values(
                deal_id=deal_id, created_at=_now(), created_by=by, commitment_doc_id=commitment_doc_id,
                contract_doc_id=contract_doc_id, updated_commitment=updated_commitment,
                analysis=analysis.model_dump(mode="json"), cost_usd=float(analysis.usage.get("cost_usd", 0.0))))
            run_id = int(res.inserted_primary_key[0])
        self.replace_items(deal_id, analysis.items, by=by)
        return run_id

    def latest_run(self, deal_id: int) -> dict | None:
        with self.engine.connect() as c:
            row = c.execute(select(runs_t).where(runs_t.c.deal_id == deal_id).order_by(runs_t.c.id.desc())
                            .limit(1)).first()
        return dict(row._mapping) if row else None

    def list_runs(self, deal_id: int) -> list[dict]:
        cols = [runs_t.c[k] for k in ("id", "created_at", "created_by", "updated_commitment", "cost_usd")]
        with self.engine.connect() as c:
            rows = c.execute(select(*cols).where(runs_t.c.deal_id == deal_id).order_by(runs_t.c.id.desc()))
            return [dict(r._mapping) for r in rows]

    def replace_items(self, deal_id: int, items: list[ActionItem], by: str = "") -> None:
        now = _now()
        with self.engine.begin() as c:
            c.execute(delete(items_t).where(items_t.c.deal_id == deal_id))
            if items:
                c.execute(insert(items_t), [{"deal_id": deal_id, "key": i.key, "position": n,
                                             "data": i.model_dump(mode="json"), "updated_at": now, "updated_by": by}
                                            for n, i in enumerate(items)])
            c.execute(update(deals_t).where(deals_t.c.id == deal_id).values(updated_at=now))

    def get_items(self, deal_id: int) -> list[ActionItem]:
        with self.engine.connect() as c:
            rows = c.execute(select(items_t.c.data).where(items_t.c.deal_id == deal_id)
                             .order_by(items_t.c.position))
            return [ActionItem.model_validate(r.data) for r in rows]

    def update_item(self, deal_id: int, key: str, by: str = "", **changes) -> None:
        with self.engine.begin() as c:
            row = c.execute(select(items_t.c.id, items_t.c.data).where(items_t.c.deal_id == deal_id,
                                                                        items_t.c.key == key)).first()
            if not row:
                return
            data = {**row.data, **changes}
            c.execute(update(items_t).where(items_t.c.id == row.id).values(data=data, updated_at=_now(),
                                                                           updated_by=by))
            c.execute(update(deals_t).where(deals_t.c.id == deal_id).values(updated_at=_now()))

    def add_item(self, deal_id: int, item: ActionItem, by: str = "") -> None:
        with self.engine.begin() as c:
            pos = c.execute(select(func.max(items_t.c.position)).where(items_t.c.deal_id == deal_id)).scalar()
            c.execute(insert(items_t).values(deal_id=deal_id, key=item.key, position=(pos or 0) + 1,
                                             data=item.model_dump(mode="json"), updated_at=_now(), updated_by=by))

    def open_items_by_deal(self) -> dict[int, list[ActionItem]]:
        """Every open deal's list (daily email, Deals page)."""
        q = (select(items_t.c.deal_id, items_t.c.data).join(deals_t, deals_t.c.id == items_t.c.deal_id)
             .where(deals_t.c.status == "open").order_by(items_t.c.deal_id, items_t.c.position))
        out: dict[int, list[ActionItem]] = {}
        with self.engine.connect() as c:
            for r in c.execute(q):
                out.setdefault(r.deal_id, []).append(ActionItem.model_validate(r.data))
        return out

    # ---- feedback and lessons
    def add_feedback(self, kind: str, text: str, by: str = "", deal_id: int | None = None,
                     item_key: str | None = None, detail: dict | None = None) -> int:
        with self.engine.begin() as c:
            res = c.execute(insert(feedback_t).values(created_at=_now(), created_by=by, deal_id=deal_id,
                                                      item_key=item_key, kind=kind, text=text, detail=detail or {},
                                                      status="pending"))
            return int(res.inserted_primary_key[0])

    def list_feedback(self, status: str | None = "pending") -> list[dict]:
        q = select(feedback_t).order_by(feedback_t.c.id.desc())
        if status:
            q = q.where(feedback_t.c.status == status)
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(q)]

    def resolve_feedback(self, feedback_id: int, approve: bool, lesson_text: str = "", by: str = "") -> int | None:
        lesson_id = self.add_lesson(lesson_text, source="feedback", by=by, approved_by=by) if approve else None
        with self.engine.begin() as c:
            c.execute(update(feedback_t).where(feedback_t.c.id == feedback_id).values(
                status="approved" if approve else "rejected", lesson_id=lesson_id))
        return lesson_id

    def add_lesson(self, text: str, source: str = "manual", by: str = "", approved_by: str = "") -> int:
        with self.engine.begin() as c:
            res = c.execute(insert(lessons_t).values(created_at=_now(), created_by=by, text=text.strip(),
                                                     source=source, active=True, approved_by=approved_by or by))
            return int(res.inserted_primary_key[0])

    def list_lessons(self, active_only: bool = False) -> list[dict]:
        q = select(lessons_t).order_by(lessons_t.c.id)
        if active_only:
            q = q.where(lessons_t.c.active.is_(True))
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(q)]

    def active_lessons(self) -> list[str]:
        """In id order, so the system prompt (and its cache) only changes when a lesson changes."""
        return [r["text"] for r in self.list_lessons(active_only=True)]

    def set_lesson(self, lesson_id: int, **fields) -> None:
        with self.engine.begin() as c:
            c.execute(update(lessons_t).where(lessons_t.c.id == lesson_id).values(**fields))

    # ---- training examples and the scorecard
    def add_example(self, name: str, document_id: int, expert_items: list[str], deal_type: str = "",
                    by: str = "") -> int:
        with self.engine.begin() as c:
            res = c.execute(insert(examples_t).values(created_at=_now(), created_by=by, name=name,
                                                      document_id=document_id, expert_items=expert_items,
                                                      deal_type=deal_type))
            return int(res.inserted_primary_key[0])

    def list_examples(self) -> list[dict]:
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(select(examples_t).order_by(examples_t.c.id))]

    def add_score(self, example_id: int, recall: float, matched: int, total: int, lessons: int) -> None:
        with self.engine.begin() as c:
            c.execute(insert(scores_t).values(example_id=example_id, run_at=_now(), recall=recall, matched=matched,
                                              total=total, lessons=lessons))

    def list_scores(self) -> list[dict]:
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(select(scores_t).order_by(scores_t.c.run_at))]
