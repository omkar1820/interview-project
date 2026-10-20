import secrets
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    interviews: Mapped[List["Interview"]] = relationship(back_populates="candidate")


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    role: Mapped[str] = mapped_column(String(120))
    num_questions: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|in_progress|completed
    access_token: Mapped[str] = mapped_column(String(64), default=lambda: secrets.token_urlsafe(18))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="interviews")
    responses: Mapped[List["Response"]] = relationship(
        back_populates="interview", order_by="Response.order_no", cascade="all, delete-orphan"
    )
    result: Mapped[Optional["FinalResult"]] = relationship(
        back_populates="interview", uselist=False, cascade="all, delete-orphan"
    )


class Response(Base):
    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), index=True)
    order_no: Mapped[int] = mapped_column(Integer)
    question_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    technical_score: Mapped[float] = mapped_column(Float, default=0)
    relevance_score: Mapped[float] = mapped_column(Float, default=0)
    problem_solving_score: Mapped[float] = mapped_column(Float, default=0)
    communication_score: Mapped[float] = mapped_column(Float, default=0)
    overall_score: Mapped[float] = mapped_column(Float, default=0)
    feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    interview: Mapped[Interview] = relationship(back_populates="responses")


class FinalResult(Base):
    __tablename__ = "final_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), unique=True)
    overall_score: Mapped[float] = mapped_column(Float)
    technical_score: Mapped[float] = mapped_column(Float)
    relevance_score: Mapped[float] = mapped_column(Float)
    problem_solving_score: Mapped[float] = mapped_column(Float)
    communication_score: Mapped[float] = mapped_column(Float)
    strengths: Mapped[str] = mapped_column(Text, default="")
    improvements: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(String(80))
    recruiter_decision: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    recruiter_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    interview: Mapped[Interview] = relationship(back_populates="result")
