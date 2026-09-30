"""Generated text, reviews, staff users and the audit log."""
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.archive import _in
from app.models.base import Base, created_at_column

ROLES = ("curator", "reviewer", "admin")
DRAFT_KINDS = ("answer", "lesson", "announcement", "social_post")
DRAFT_STATUSES = ("ai_draft", "auto_checked", "approved", "rejected", "published")
CHECK_RESULTS = ("supported", "partial", "unsupported")
DECISIONS = ("approve", "reject", "edit", "publish")


class User(Base):
    """Staff account. The public never logs in."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint(_in("role", ROLES), name="role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_at_column()


class Draft(Base):
    __tablename__ = "drafts"
    __table_args__ = (
        CheckConstraint(_in("kind", DRAFT_KINDS), name="kind"),
        CheckConstraint(_in("status", DRAFT_STATUSES), name="status"),
        CheckConstraint("language IN ('en', 'hi')", name="language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    audience: Mapped[str | None] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(5), default="en")
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="ai_draft")
    created_by: Mapped[str] = mapped_column(String(100))
    # Inputs the generator was given (selected chunk ids, topic, level, ...).
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    expedition_id: Mapped[int | None] = mapped_column(ForeignKey("expeditions.id"))
    # The English draft this one translates.
    translation_of_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id"))
    # For corrections: the published draft this version replaces.
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    correction_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sentences: Mapped[list["DraftSentence"]] = relationship(
        back_populates="draft", order_by="DraftSentence.seq", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(back_populates="draft", order_by="Review.created_at")


class DraftSentence(Base):
    __tablename__ = "draft_sentences"
    __table_args__ = (
        UniqueConstraint("draft_id", "seq"),
        CheckConstraint(
            "check_result IS NULL OR " + _in("check_result", CHECK_RESULTS), name="check_result"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    # Lesson/announcement section this sentence belongs to (e.g. "starter", "quiz", "web_post").
    section: Mapped[str | None] = mapped_column(String(50))
    text: Mapped[str] = mapped_column(Text)
    # False for questions and instructions ("Discuss with a partner..."): nothing to fact-check.
    is_claim: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    cited_chunk_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    check_result: Mapped[str | None] = mapped_column(String(20))
    check_reason: Mapped[str | None] = mapped_column(Text)
    edited_by: Mapped[str | None] = mapped_column(String(100))

    draft: Mapped[Draft] = relationship(back_populates="sentences")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint(_in("decision", DECISIONS), name="decision"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id"))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewer_name: Mapped[str] = mapped_column(String(100))
    decision: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()

    draft: Mapped[Draft] = relationship(back_populates="reviews")


class AuditLog(Base):
    """Append-only. A database trigger (see migration) rejects UPDATE and DELETE."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = created_at_column()
