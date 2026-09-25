from datetime import datetime, timezone
import enum
from typing import List, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DifficultyLevel(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    MIXED = "mixed"


class PaperStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class QuestionType(str, enum.Enum):
    MCQ = "mcq"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    TRUE_FALSE = "true_false"
    FORMULA_BASED = "formula_based"


class QuestionPaper(Base):
    __tablename__ = "question_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_grade: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    difficulty_level: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel), default=DifficultyLevel.MEDIUM, nullable=False
    )
    total_marks: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[PaperStatus] = mapped_column(
        Enum(PaperStatus), default=PaperStatus.PENDING, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    document: Mapped[Optional["Document"]] = relationship("Document", back_populates="question_papers")
    questions: Mapped[List["Question"]] = relationship(
        "Question",
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="Question.question_number",
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("question_papers.id", ondelete="CASCADE"), nullable=False
    )
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType), nullable=False)
    difficulty: Mapped[DifficultyLevel] = mapped_column(Enum(DifficultyLevel), nullable=False)
    options: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # e.g., {"A": "...", "B": "..."}
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    marks: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    formula_latex: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_reference: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Relationship
    paper: Mapped["QuestionPaper"] = relationship("QuestionPaper", back_populates="questions")
