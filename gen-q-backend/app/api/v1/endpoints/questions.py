from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.document import Document
from app.models.question_paper import PaperStatus, Question, QuestionPaper
from app.schemas.question_paper import (
    GenerateQuestionPaperRequest,
    QuestionPaperResponse,
    QuestionPaperSummary,
    QuestionSchema,
)
from app.services.ollama_service import OllamaServiceException
from app.services.question_generator import question_generator_service

router = APIRouter(prefix="/questions", tags=["Question Generation & Assessment"])


@router.post(
    "/generate",
    response_model=QuestionPaperResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a question paper using Gemma from an uploaded document or raw text",
)
async def generate_question_paper(
    request: GenerateQuestionPaperRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate high-quality question paper using local Ollama (Gemma) with custom difficulty,
    question distribution, and math formulas extracted from source material."""
    context_text = ""
    formulas = []
    images = []

    # 1. Retrieve document content if document_id is provided
    if request.document_id:
        stmt = (
            select(Document)
            .where(Document.id == request.document_id)
            .options(selectinload(Document.extract))
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {request.document_id} not found",
            )
        if not doc.extract:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected document has no extracted text",
            )
        context_text = doc.extract.raw_text
        formulas = doc.extract.formulas or []
        images = doc.extract.images or []
    elif request.raw_text:
        context_text = request.raw_text
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'document_id' or 'raw_text' must be provided to generate questions",
        )

    # 2. Create pending QuestionPaper record in database
    paper = QuestionPaper(
        document_id=request.document_id,
        title=request.title,
        subject=request.subject,
        target_grade=request.target_grade,
        difficulty_level=request.difficulty_level,
        total_marks=request.total_marks,
        status=PaperStatus.GENERATING,
    )
    db.add(paper)
    await db.commit()
    await db.refresh(paper)

    # 3. Call Question Generator (Ollama Gemma)
    try:
        generated_questions: List[QuestionSchema] = (
            await question_generator_service.generate_questions_from_context(
                request=request,
                context_text=context_text,
                formulas=formulas,
                images=images,
            )
        )

        # 4. Save generated questions to DB
        actual_total_marks = 0
        for q_data in generated_questions:
            actual_total_marks += q_data.marks
            q_db = Question(
                paper_id=paper.id,
                question_number=q_data.question_number,
                question_text=q_data.question_text,
                question_type=q_data.question_type,
                difficulty=q_data.difficulty,
                options=q_data.options,
                correct_answer=q_data.correct_answer,
                explanation=q_data.explanation,
                marks=q_data.marks,
                formula_latex=q_data.formula_latex,
                image_reference=q_data.image_reference,
            )
            db.add(q_db)

        paper.total_questions = len(generated_questions)
        paper.total_marks = actual_total_marks or request.total_marks
        paper.status = PaperStatus.COMPLETED
        await db.commit()

    except OllamaServiceException as o_err:
        paper.status = PaperStatus.FAILED
        paper.error_message = o_err.message
        await db.commit()
        raise HTTPException(status_code=o_err.status_code, detail=o_err.message)
    except Exception as exc:
        paper.status = PaperStatus.FAILED
        paper.error_message = str(exc)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Question generation error: {str(exc)}",
        )

    # 5. Return complete paper response
    stmt = (
        select(QuestionPaper)
        .where(QuestionPaper.id == paper.id)
        .options(selectinload(QuestionPaper.questions))
    )
    result = await db.execute(stmt)
    full_paper = result.scalar_one()
    return full_paper


@router.get(
    "/papers",
    response_model=List[QuestionPaperSummary],
    summary="List all generated question papers",
)
async def list_question_papers(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(QuestionPaper)
        .offset(skip)
        .limit(limit)
        .order_by(QuestionPaper.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/papers/{paper_id}",
    response_model=QuestionPaperResponse,
    summary="Get full details of a question paper including questions, answers, and solutions",
)
async def get_question_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(QuestionPaper)
        .where(QuestionPaper.id == paper_id)
        .options(selectinload(QuestionPaper.questions))
    )
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question paper with ID {paper_id} not found",
        )
    return paper


@router.delete(
    "/papers/{paper_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a question paper and its questions",
)
async def delete_question_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(QuestionPaper).where(QuestionPaper.id == paper_id)
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question paper with ID {paper_id} not found",
        )

    await db.delete(paper)
    await db.commit()
