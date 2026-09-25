from datetime import datetime, timezone
import enum
from typing import List, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FileType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[FileType] = mapped_column(Enum(FileType), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # in bytes
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    extract: Mapped[Optional["DocumentExtract"]] = relationship(
        "DocumentExtract",
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False,
    )
    question_papers: Mapped[List["QuestionPaper"]] = relationship(
        "QuestionPaper",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentExtract(Base):
    __tablename__ = "document_extracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    formulas: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    images: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_words: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_formulas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_images: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    document: Mapped["Document"] = relationship("Document", back_populates="extract")
