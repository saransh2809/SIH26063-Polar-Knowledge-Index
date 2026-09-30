"""Staff endpoints: login, curator link confirmation, draft generation and the review queue."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import serializers as S
from app.core.db import get_db
from app.core.security import create_token, require_role, verify_password
from app.models import AuditLog, Chunk, Draft, Expedition, Item, ItemLink, Station, Topic, User
from app.services import audit, drafts, generators

router = APIRouter(tags=["staff"])
any_staff = require_role("curator", "reviewer")
curator = require_role("curator")
reviewer = require_role("reviewer")


# --- auth ---------------------------------------------------------------------------------
@router.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.username == form.username, User.is_active.is_(True)))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Wrong username or password")
    audit.record(db, user.display_name, "login", "user", user.id)
    db.commit()
    return {"access_token": create_token(user), "token_type": "bearer",
            "user": {"username": user.username, "display_name": user.display_name, "role": user.role}}


@router.get("/auth/me")
def me(user: User = Depends(any_staff)) -> dict:
    return {"username": user.username, "display_name": user.display_name, "role": user.role}


# --- curator: links ---------------------------------------------------------------------------
@router.get("/staff/links")
def list_links(status: str = "unconfirmed", limit: int = 100, db: Session = Depends(get_db),
               user: User = Depends(any_staff)) -> dict:
    q = select(ItemLink).where(ItemLink.status == status).order_by(ItemLink.created_at, ItemLink.id)
    total = db.scalar(select(func.count()).select_from(ItemLink).where(ItemLink.status == status))
    links = db.scalars(q.limit(limit)).all()
    return {"total": total, "links": [{**S.link(l), "item": S.item_summary(l.item)} for l in links]}


class LinkDecision(BaseModel):
    comment: str | None = None


def _decide_link(db: Session, link_id: int, user: User, status: str, comment: str | None) -> dict:
    link = db.get(ItemLink, link_id)
    if link is None:
        raise HTTPException(404, "Link not found")
    before = link.status
    link.status, link.confirmed_by, link.confirmed_at = status, user.display_name, datetime.now(timezone.utc)
    audit.record(db, user.display_name, f"link_{status}", "item_link", link.id, before=before, comment=comment,
                 item_id=link.item_id, link_type=link.link_type)
    db.commit()
    return S.link(link)


@router.post("/staff/links/{link_id}/confirm")
def confirm_link(link_id: int, body: LinkDecision | None = None, db: Session = Depends(get_db),
                 user: User = Depends(curator)) -> dict:
    return _decide_link(db, link_id, user, "confirmed", body.comment if body else None)


@router.post("/staff/links/{link_id}/reject")
def reject_link(link_id: int, body: LinkDecision | None = None, db: Session = Depends(get_db),
                user: User = Depends(curator)) -> dict:
    return _decide_link(db, link_id, user, "rejected", body.comment if body else None)


class NewLink(BaseModel):
    item_id: int
    link_type: str = Field(pattern="^(expedition|station|topic|year)$")
    target: str  # expedition code, station name, topic key, or year


@router.post("/staff/links")
def add_link(body: NewLink, db: Session = Depends(get_db), user: User = Depends(curator)) -> dict:
    """A curator's correction: adds a confirmed manual link."""
    if db.get(Item, body.item_id) is None:
        raise HTTPException(404, "Item not found")
    link = ItemLink(item_id=body.item_id, link_type=body.link_type, method="manual", status="confirmed",
                    confirmed_by=user.display_name, confirmed_at=datetime.now(timezone.utc),
                    evidence=f"added by curator {user.display_name}")
    if body.link_type == "expedition":
        target = db.scalar(select(Expedition).where(Expedition.code == body.target.upper()))
        link.expedition_id = target.id if target else None
    elif body.link_type == "station":
        target = db.scalar(select(Station).where(Station.name == body.target))
        link.station_id = target.id if target else None
    elif body.link_type == "topic":
        target = db.scalar(select(Topic).where(Topic.key == body.target))
        link.topic_id = target.id if target else None
    else:
        target = int(body.target) if body.target.isdigit() else None
        link.year = target
    if target is None:
        raise HTTPException(400, f"Unknown {body.link_type}: {body.target}")
    db.add(link)
    db.flush()
    audit.record(db, user.display_name, "link_added", "item_link", link.id, item_id=body.item_id,
                 link_type=body.link_type, target=body.target)
    db.commit()
    return S.link(link)


# --- drafts: generation ------------------------------------------------------------------------
class QuestionIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    audience: str = "student"


@router.post("/staff/answers")
def draft_answer(body: QuestionIn, db: Session = Depends(get_db), user: User = Depends(any_staff)) -> dict:
    hits, relevant, reason = generators.retrieve_for_question(db, body.question)
    if not relevant:
        audit.record(db, user.display_name, "question_refused", "question", None, question=body.question, reason=reason)
        db.commit()
        return {"status": "refused", "message": generators.REFUSAL, "reason": reason,
                "passages": [S.hit(h) for h in hits[:3]]}
    d = generators.draft_answer(db, body.question, hits, created_by=user.display_name, audience=body.audience)
    if d is None:
        audit.record(db, user.display_name, "question_refused", "question", None, question=body.question,
                     reason="model: passages do not answer the question")
        db.commit()
        return {"status": "refused", "message": generators.REFUSAL,
                "reason": "Passages were retrieved, but none of them answers the question.",
                "passages": [S.hit(h) for h in hits[:3]]}
    db.commit()
    return {"status": "drafted", "reason": reason, "draft": S.draft(db, d), "passages": [S.hit(h) for h in hits[:5]]}


class LessonIn(BaseModel):
    chunk_ids: list[int] = Field(min_length=1, max_length=20)
    topic: str = Field(min_length=2, max_length=200)
    level: str = Field(default="Class 11", max_length=50)


@router.post("/staff/drafts/lesson")
def draft_lesson(body: LessonIn, db: Session = Depends(get_db), user: User = Depends(any_staff)) -> dict:
    d = generators.generate_lesson(db, body.chunk_ids, body.topic, body.level, created_by=user.display_name)
    db.commit()
    return S.draft(db, d)


class AnnouncementIn(BaseModel):
    expedition_code: str
    angle: str | None = Field(default=None, max_length=300)


@router.post("/staff/drafts/announcement")
def draft_announcement(body: AnnouncementIn, db: Session = Depends(get_db), user: User = Depends(any_staff)) -> dict:
    e = db.scalar(select(Expedition).where(Expedition.code == body.expedition_code.upper()))
    if e is None:
        raise HTTPException(404, "Expedition not found")
    d = generators.generate_announcement(db, e, created_by=user.display_name, angle=body.angle)
    db.commit()
    return S.draft(db, d)


def _draft(db: Session, draft_id: int) -> Draft:
    d = db.get(Draft, draft_id)
    if d is None:
        raise HTTPException(404, "Draft not found")
    return d


@router.post("/staff/drafts/{draft_id}/translate")
def translate(draft_id: int, db: Session = Depends(get_db), user: User = Depends(any_staff)) -> dict:
    d = generators.translate_to_hindi(db, _draft(db, draft_id), created_by=user.display_name)
    db.commit()
    return S.draft(db, d)


# --- drafts: review ---------------------------------------------------------------------------------
@router.get("/staff/drafts")
def list_drafts(status: str | None = None, kind: str | None = None, db: Session = Depends(get_db),
                user: User = Depends(any_staff)) -> list[dict]:
    q = select(Draft)
    if status:
        q = q.where(Draft.status.in_(status.split(",")))
    if kind:
        q = q.where(Draft.kind == kind)
    return [S.draft(db, d, with_sources=False) for d in db.scalars(q.order_by(Draft.created_at.desc()).limit(200))]


@router.get("/staff/drafts/{draft_id}")
def get_draft(draft_id: int, db: Session = Depends(get_db), user: User = Depends(any_staff)) -> dict:
    return S.draft(db, _draft(db, draft_id))


@router.post("/staff/drafts/{draft_id}/recheck")
def recheck(draft_id: int, db: Session = Depends(get_db), user: User = Depends(any_staff)) -> dict:
    d = _draft(db, draft_id)
    if d.status not in drafts.EDITABLE:
        raise drafts.WorkflowError(f"Cannot re-check a draft in status '{d.status}'.")
    drafts.check_draft(db, d, actor=user.display_name)
    db.commit()
    return S.draft(db, d)


class SentenceEdit(BaseModel):
    text: str | None = Field(default=None, max_length=2000)
    citations: list[int] | None = None


@router.patch("/staff/drafts/{draft_id}/sentences/{sentence_id}")
def edit_sentence(draft_id: int, sentence_id: int, body: SentenceEdit, db: Session = Depends(get_db),
                  user: User = Depends(any_staff)) -> dict:
    d = _draft(db, draft_id)
    drafts.edit_sentence(db, d, sentence_id, user, body.text, body.citations)
    db.commit()
    return S.draft(db, d)


@router.delete("/staff/drafts/{draft_id}/sentences/{sentence_id}")
def delete_sentence(draft_id: int, sentence_id: int, db: Session = Depends(get_db),
                    user: User = Depends(any_staff)) -> dict:
    d = _draft(db, draft_id)
    drafts.delete_sentence(db, d, sentence_id, user)
    db.commit()
    return S.draft(db, d)


class DecisionIn(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


@router.post("/staff/drafts/{draft_id}/approve")
def approve(draft_id: int, body: DecisionIn | None = None, db: Session = Depends(get_db),
            user: User = Depends(reviewer)) -> dict:
    d = drafts.approve(db, _draft(db, draft_id), user, body.comment if body else None)
    db.commit()
    return S.draft(db, d)


@router.post("/staff/drafts/{draft_id}/reject")
def reject(draft_id: int, body: DecisionIn | None = None, db: Session = Depends(get_db),
           user: User = Depends(reviewer)) -> dict:
    d = drafts.reject(db, _draft(db, draft_id), user, body.comment if body else None)
    db.commit()
    return S.draft(db, d)


@router.post("/staff/drafts/{draft_id}/publish")
def publish(draft_id: int, db: Session = Depends(get_db), user: User = Depends(reviewer)) -> dict:
    d = drafts.publish(db, _draft(db, draft_id), user)
    db.commit()
    return S.draft(db, d)


class CorrectionIn(BaseModel):
    note: str = Field(min_length=5, max_length=1000)


@router.post("/staff/drafts/{draft_id}/correct")
def correct(draft_id: int, body: CorrectionIn, db: Session = Depends(get_db), user: User = Depends(reviewer)) -> dict:
    d = drafts.start_correction(db, _draft(db, draft_id), user, body.note)
    db.commit()
    return S.draft(db, d)


# --- sources picker and audit ----------------------------------------------------------------------
@router.get("/staff/chunks/{chunk_id}")
def chunk(chunk_id: int, db: Session = Depends(get_db), user: User = Depends(any_staff)) -> dict:
    c = db.get(Chunk, chunk_id)
    if c is None:
        raise HTTPException(404, "Chunk not found")
    return S.citation(c)


@router.get("/staff/audit")
def audit_log(limit: int = 100, target_type: str | None = None, target_id: int | None = None,
              db: Session = Depends(get_db), user: User = Depends(any_staff)) -> list[dict]:
    q = select(AuditLog)
    if target_type:
        q = q.where(AuditLog.target_type == target_type)
    if target_id is not None:
        q = q.where(AuditLog.target_id == target_id)
    rows = db.scalars(q.order_by(AuditLog.id.desc()).limit(min(limit, 500))).all()
    return [{"id": a.id, "actor": a.actor, "action": a.action, "target_type": a.target_type,
             "target_id": a.target_id, "details": a.details, "at": a.created_at.isoformat()} for a in rows]
