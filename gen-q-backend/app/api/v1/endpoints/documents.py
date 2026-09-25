import os
from pathlib import Path
import shutil
from typing import List
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.document import Document, DocumentExtract, FileType
from app.schemas.document import DocumentDetailRead, DocumentRead, ParsedDocumentResult
from app.services.document_parser import document_parser_service

router = APIRouter(prefix="/documents", tags=["Documents & Multimodal Extraction"])

ALLOWED_EXTENSIONS = {".pdf": FileType.PDF, ".docx": FileType.DOCX, ".txt": FileType.TXT, ".md": FileType.MD}


@router.post(
    "/upload",
    response_model=DocumentDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document and extract separated text, math formulas, and images",
)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF, DOCX, TXT, or MD document. The system automatically extracts text,
    detects LaTeX & mathematical formulas, and saves embedded images."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{suffix}'. Allowed formats: PDF, DOCX, TXT, MD",
        )

    # Save uploaded file
    upload_dir = settings.upload_path / "files"
    upload_dir.mkdir(parents=True, exist_ok=True)
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    saved_file_path = upload_dir / unique_filename

    try:
        with open(saved_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}",
        )

    file_size = os.path.getsize(saved_file_path)

    # Parse and separate content
    try:
        parsed: ParsedDocumentResult = document_parser_service.parse_file(saved_file_path)
    except Exception as e:
        if saved_file_path.exists():
            saved_file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse document: {str(e)}",
        )

    # Save to PostgreSQL
    doc_record = Document(
        filename=file.filename or "unknown",
        file_type=ALLOWED_EXTENSIONS[suffix],
        file_size=file_size,
        file_path=str(saved_file_path).replace("\\", "/"),
    )
    db.add(doc_record)
    await db.flush()

    extract_record = DocumentExtract(
        document_id=doc_record.id,
        raw_text=parsed.full_text,
        formulas=[f.model_dump() for f in parsed.formulas],
        images=[img.model_dump() for img in parsed.images],
        total_words=parsed.word_count,
        total_formulas=parsed.total_formulas,
        total_images=parsed.total_images,
    )
    db.add(extract_record)
    await db.commit()
    await db.refresh(doc_record, attribute_names=["extract"])

    return doc_record


@router.get(
    "",
    response_model=List[DocumentRead],
    summary="List all uploaded documents",
)
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).offset(skip).limit(limit).order_by(Document.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/{document_id}",
    response_model=DocumentDetailRead,
    summary="Get document details with extracted text, formulas, and images",
)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.extract))
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )
    return doc


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an uploaded document and its extracted content",
)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )

    # Remove physical file if exists
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            pass

    await db.delete(doc)
    await db.commit()
