from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column


class EvalQuestion(Base):
    """A test question. Only rows with `verified_by` set count toward the score."""

    __tablename__ = "eval_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answerable: Mapped[bool] = mapped_column(Boolean)
    expected_answer: Mapped[str | None] = mapped_column(Text)
    expected_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))
    expected_page: Mapped[int | None] = mapped_column(Integer)
    verified_by: Mapped[str | None] = mapped_column(String(100))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
