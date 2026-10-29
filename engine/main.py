"""Title Agent engine (v2, docs/PLAN-v2.md): the private service behind title.totalchb.com.

It holds the AI key and runs everything that needs the server: reading commitments, reviews, training comparisons,
exports, and every change to the data (the page reads Firestore live; the security rules keep it read-only). Every
request carries the person's Firebase ID token; only verified accounts on ALLOWED_DOMAINS (default totalchb.com) or
in ALLOWED_EMAILS get in. Admin actions also need the email in Settings → Admins (no admins yet = everyone).

Long steps (read, review, re-run, training) take 1–3 minutes: the page sends a job id, watches jobs/{id} in
Firestore for the current step, and gets the result in the response (Cloud Run timeout 15 minutes).

    uv run uvicorn engine.main:app --port 8080
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from titleagent import flows
from titleagent.access import email_allowed
from titleagent.config import DEFAULT_SETTINGS, Secrets, load_secrets
from titleagent.exports import INCLUDE, checklist_for, google
from titleagent.llm import LLM, AgentError, ClaudeLLM
from titleagent.models import STATUSES
from titleagent.storage import open_store

log = logging.getLogger("engine")
JOB_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


# ---------------------------------------------------------------- wiring (replaced in tests)
@dataclass
class Engine:
    secrets: Secrets
    store: object  # FirestoreStore in the cloud; any store in tests
    llm: Callable[[], LLM]
    verify: Callable[[str], dict]  # Firebase ID token -> claims


def _firebase_verify(secrets: Secrets) -> Callable[[str], dict]:
    import firebase_admin
    from firebase_admin import auth, credentials

    if not firebase_admin._apps:
        cred = (credentials.Certificate(secrets.firebase_credentials) if secrets.firebase_credentials
                else credentials.ApplicationDefault())
        firebase_admin.initialize_app(cred, {"projectId": secrets.firebase_project})
    return lambda token: auth.verify_id_token(token)


def default_engine() -> Engine:
    secrets = load_secrets()
    return Engine(secrets=secrets, store=open_store(secrets), llm=lambda: ClaudeLLM(secrets.anthropic_api_key or ""),
                  verify=_firebase_verify(secrets))


@dataclass
class User:
    email: str
    uid: str
    admin: bool


# ---------------------------------------------------------------- request bodies
class ReadIn(BaseModel):
    job_id: str
    commitment_path: str
    commitment_name: str = "Commitment.pdf"
    contract_path: str | None = None
    contract_name: str = "Contract.pdf"
    update_for: int | None = None

class ReviewIn(BaseModel):
    job_id: str
    draft_id: str
    fields: dict

class JobIn(BaseModel):
    job_id: str

class TrainIn(BaseModel):
    job_id: str
    path: str
    filename: str = "Commitment.pdf"
    deal_type: str = ""
    name: str = ""
    expert: list[str] = []

class GoogleIn(BaseModel):
    kind: Literal["sheet", "doc"]
    include: str = "all"

class MissingIn(BaseModel):
    what: str
    where: str = ""
    why: str = ""
    priority: Literal["blocker", "before", "fyi"] = "blocker"
    provided_by: str = "Seller"
    add_to_list: bool = True

class DealPatch(BaseModel):
    status: Literal["open", "closed"]

class ItemPatch(BaseModel):
    key: str
    status: str | None = None
    due_date: str | None = Field(default=None, description="YYYY-MM-DD, or empty to clear")
    notes: str | None = None

class ItemFeedbackIn(BaseModel):
    item_key: str
    kind: Literal["not_needed", "wrong"]
    note: str = ""

class ResolveIn(BaseModel):
    approve: bool
    lesson: str = ""

class LessonIn(BaseModel):
    text: str

class LessonPatch(BaseModel):
    text: str | None = None
    active: bool | None = None


# ---------------------------------------------------------------- app
def create_app(engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="Title Agent engine", docs_url=None, redoc_url=None, openapi_url=None)
    origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "https://title.totalchb.com").split(",")
               if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"],
                       expose_headers=["Content-Disposition"])
    state = {"engine": engine}

    def eng() -> Engine:
        if state["engine"] is None:
            state["engine"] = default_engine()
        return state["engine"]

    def user(authorization: str = Header(default=""), e: Engine = Depends(eng)) -> User:
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise HTTPException(401, "Sign in first.")
        try:
            claims = e.verify(token)
        except Exception as exc:
            raise HTTPException(401, "Your sign-in has expired. Sign in again.") from exc
        email = str(claims.get("email") or "").lower()
        s = e.secrets
        if not (claims.get("email_verified") and email_allowed(email, s.allowed_emails, s.allowed_domains)):
            raise HTTPException(403, f"{email or 'This account'} doesn't have access to the Title Agent.")
        admins = [a.strip().lower() for a in e.store.get_settings().get("admins", []) if a.strip()]
        return User(email=email, uid=str(claims.get("uid") or claims.get("user_id") or ""),
                    admin=not admins or email in admins)

    def admin(u: User = Depends(user)) -> User:
        if not u.admin:
            raise HTTPException(403, "Only admins can do this (Settings → Admins).")
        return u

    @app.exception_handler(flows.FlowError)
    def flow_error(_: Request, exc: flows.FlowError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(AgentError)
    def agent_error(_: Request, exc: AgentError):
        return JSONResponse({"detail": str(exc)}, status_code=502)

    # ---- jobs: the step the page shows while the agent works
    def job(e: Engine, job_id: str, kind: str, u: User):
        if not JOB_ID.match(job_id or ""):
            raise HTTPException(400, "Missing or invalid job id.")
        db = getattr(e.store, "db", None)
        ref = db.document(f"jobs/{job_id}") if db else None
        now = datetime.now(UTC)
        if ref:
            ref.set({"id": job_id, "kind": kind, "by": u.email, "status": "running", "step": "Starting",
                     "created_at": now, "updated_at": now})

        def progress(step: str) -> None:
            if ref:
                ref.update({"step": step, "updated_at": datetime.now(UTC)})

        def finish(status: str, detail: str = "") -> None:
            if ref:
                ref.update({"status": status, "step": detail or ("Done" if status == "done" else "Stopped"),
                            "updated_at": datetime.now(UTC)})

        return progress, finish

    def run_job(e: Engine, job_id: str, kind: str, u: User, fn: Callable[[Callable[[str], None]], object]):
        progress, finish = job(e, job_id, kind, u)
        try:
            out = fn(progress)
        except (flows.FlowError, AgentError) as exc:
            finish("error", str(exc))
            raise
        except Exception as exc:
            log.exception("job %s (%s) failed", job_id, kind)
            finish("error", "Something went wrong. Try again; if it keeps happening, tell an admin.")
            raise HTTPException(500, "Something went wrong. Try again; if it keeps happening, tell an admin.") \
                from exc
        finish("done")
        return out

    def upload(e: Engine, u: User, path: str) -> bytes:
        """Files the page put in Storage under uploads/<the person's uid>/ (and nowhere else)."""
        if not u.uid or not path.startswith(f"uploads/{u.uid}/") or ".." in path:
            raise HTTPException(400, "That upload isn't yours.")
        try:
            return e.store.blobs.get(path)
        except Exception as exc:
            raise HTTPException(400, "The upload wasn't found. Upload the file again.") from exc

    def deal_or_404(e: Engine, deal_id: int) -> dict:
        deal = e.store.get_deal(deal_id)
        if not deal:
            raise HTTPException(404, "That deal doesn't exist.")
        return deal

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/v1/me")
    def me(u: User = Depends(user)):
        return {"email": u.email, "admin": u.admin}

    @app.post("/v1/read")
    def read(body: ReadIn, u: User = Depends(user), e: Engine = Depends(eng)):
        commitment = upload(e, u, body.commitment_path)
        contract = upload(e, u, body.contract_path) if body.contract_path else None

        def go(progress):
            draft = flows.read(e.store, e.llm(), commitment, body.commitment_name, u.email, contract,
                               body.contract_name, body.update_for, progress)
            draft_id = e.store.save_draft(draft, u.email)
            for p in filter(None, (body.commitment_path, body.contract_path)):
                e.store.blobs.delete(p)
            return {"draft_id": draft_id, "prefill": draft["prefill"], "summary": draft["summary"],
                    "update_for": draft["update_for"]}

        return run_job(e, body.job_id, "read", u, go)

    @app.post("/v1/review")
    def review(body: ReviewIn, u: User = Depends(user), e: Engine = Depends(eng)):
        draft = e.store.get_draft(body.draft_id)
        if not draft:
            raise HTTPException(404, "That upload has expired. Start over from Analyze.")

        def go(progress):
            deal_id = flows.review(e.store, e.llm(), draft, body.fields, u.email, progress)
            e.store.delete_draft(body.draft_id)
            return {"deal_id": deal_id}

        return run_job(e, body.job_id, "review", u, go)

    @app.post("/v1/deals/{deal_id}/rerun")
    def rerun(deal_id: int, body: JobIn, u: User = Depends(user), e: Engine = Depends(eng)):
        deal_or_404(e, deal_id)
        return run_job(e, body.job_id, "rerun", u,
                       lambda progress: {"deal_id": flows.rerun(e.store, e.llm(), deal_id, u.email, progress)})

    @app.post("/v1/training")
    def train(body: TrainIn, u: User = Depends(user), e: Engine = Depends(eng)):
        data = upload(e, u, body.path)

        def go(progress):
            out = flows.train(e.store, e.llm(), data, body.filename, body.deal_type, body.name,
                              [x.strip() for x in body.expert if x.strip()], u.email, progress)
            e.store.blobs.delete(body.path)
            return out

        return run_job(e, body.job_id, "training", u, go)

    @app.get("/v1/deals/{deal_id}/export")
    def export(deal_id: int, format: str = "pdf", include: str = "all", u: User = Depends(user),
               e: Engine = Depends(eng)):
        data, name, mime = flows.export(e.store, deal_id, format, include)
        return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.post("/v1/deals/{deal_id}/google")
    def to_google(deal_id: int, body: GoogleIn, u: User = Depends(user), e: Engine = Depends(eng)):
        if body.include not in INCLUDE:
            raise HTTPException(400, f"Unknown choice: {body.include}.")
        deal = deal_or_404(e, deal_id)
        run = e.store.latest_run(deal_id)
        checklist = checklist_for(deal, run["analysis"] if run else None, e.store.get_items(deal_id))
        data = flows.export(e.store, deal_id, "xlsx" if body.kind == "sheet" else "docx", body.include)[0]
        try:
            link = google.export(e.secrets, e.store.get_settings().get("google_folder_id", ""),
                                 f"{checklist.title} · {checklist.heading(body.include)}", data, body.kind)
        except google.GoogleExportError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"link": link}

    @app.post("/v1/deals/{deal_id}/missing")
    def missing(deal_id: int, body: MissingIn, u: User = Depends(user), e: Engine = Depends(eng)):
        deal_or_404(e, deal_id)
        return {"feedback_id": flows.missing_item(e.store, deal_id, body.what, body.where, body.why, body.priority,
                                                  body.provided_by, u.email, body.add_to_list)}

    @app.patch("/v1/deals/{deal_id}")
    def set_deal(deal_id: int, body: DealPatch, u: User = Depends(user), e: Engine = Depends(eng)):
        deal_or_404(e, deal_id)
        e.store.update_deal(deal_id, status=body.status)
        return {"ok": True}

    @app.patch("/v1/deals/{deal_id}/items")
    def set_item(deal_id: int, body: ItemPatch, u: User = Depends(user), e: Engine = Depends(eng)):
        deal_or_404(e, deal_id)
        if not any(i.key == body.key for i in e.store.get_items(deal_id)):
            raise HTTPException(404, "That item isn't on this deal's list.")
        changes: dict = {}
        if body.status is not None:
            if body.status not in STATUSES:
                raise HTTPException(400, f"Status must be one of: {', '.join(STATUSES)}.")
            changes["status"] = body.status
        if body.due_date is not None:
            try:
                changes["due_date"] = date.fromisoformat(body.due_date).isoformat() if body.due_date else None
            except ValueError as exc:
                raise HTTPException(400, "Due date must be YYYY-MM-DD.") from exc
        if body.notes is not None:
            changes["notes"] = body.notes[:2000]
        if changes:
            e.store.update_item(deal_id, body.key, by=u.email, **changes)
        return {"ok": True}

    @app.post("/v1/deals/{deal_id}/feedback")
    def item_feedback(deal_id: int, body: ItemFeedbackIn, u: User = Depends(user), e: Engine = Depends(eng)):
        deal_or_404(e, deal_id)
        titles = {i.key: i.title for i in e.store.get_items(deal_id)}
        if body.item_key not in titles:
            raise HTTPException(404, "That item isn't on this deal's list.")
        text = f"{titles[body.item_key]}: {body.note}".strip(": ")
        return {"feedback_id": e.store.add_feedback(body.kind, text, by=u.email, deal_id=deal_id,
                                                    item_key=body.item_key, detail={"note": body.note})}

    # ---- admins
    @app.post("/v1/feedback/{feedback_id}/resolve")
    def resolve(feedback_id: int, body: ResolveIn, u: User = Depends(admin), e: Engine = Depends(eng)):
        if body.approve and not body.lesson.strip():
            raise HTTPException(400, "Write the lesson as a general rule before approving it.")
        return {"lesson_id": e.store.resolve_feedback(feedback_id, body.approve, body.lesson, by=u.email)}

    @app.post("/v1/lessons")
    def add_lesson(body: LessonIn, u: User = Depends(admin), e: Engine = Depends(eng)):
        if not body.text.strip():
            raise HTTPException(400, "Write the lesson first.")
        return {"lesson_id": e.store.add_lesson(body.text, source="manual", by=u.email)}

    @app.patch("/v1/lessons/{lesson_id}")
    def set_lesson(lesson_id: int, body: LessonPatch, u: User = Depends(admin), e: Engine = Depends(eng)):
        fields = {k: v for k, v in (("text", body.text and body.text.strip()), ("active", body.active))
                  if v is not None and v != ""}
        if fields:
            e.store.set_lesson(lesson_id, **fields)
        return {"ok": True}

    @app.put("/v1/settings")
    def put_settings(body: dict, u: User = Depends(admin), e: Engine = Depends(eng)):
        unknown = set(body) - (set(DEFAULT_SETTINGS) - {"our_entities"})
        if unknown:
            raise HTTPException(400, f"Unknown settings: {', '.join(sorted(unknown))}.")
        for key, value in body.items():
            if key == "google_folder_id":
                value = google.folder_id_from(str(value or ""))
            if key == "due_offsets":
                value = {k: int(v) for k, v in dict(value).items() if k in DEFAULT_SETTINGS["due_offsets"]}
            e.store.set_setting(key, value, by=u.email)
        return {"ok": True}

    @app.post("/v1/google/check")
    def google_check(u: User = Depends(admin), e: Engine = Depends(eng)):
        ok, message = google.check(e.secrets, e.store.get_settings().get("google_folder_id", ""))
        return {"ok": ok, "message": message}

    return app


app = create_app()
