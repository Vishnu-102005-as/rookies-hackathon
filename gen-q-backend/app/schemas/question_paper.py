from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.question_paper import DifficultyLevel, PaperStatus, QuestionType


class QuestionTypesDistribution(BaseModel):
    mcq: Optional[int] = Field(default=5, description="Number of Multiple Choice Questions")
    short_answer: Optional[int] = Field(default=3, description="Number of Short Answer Questions")
    long_answer: Optional[int] = Field(default=2, description="Number of Long / Descriptive Questions")
    formula_based: Optional[int] = Field(default=2, description="Number of Numerical / Formula-based Questions")
    true_false: Optional[int] = Field(default=0, description="Number of True/False Questions")


class GenerateQuestionPaperRequest(BaseModel):
    document_id: Optional[int] = Field(
        default=None, description="ID of uploaded document from which to extract content"
    )
    raw_text: Optional[str] = Field(
        default=None, description="Direct text input if generating without an uploaded document"
    )
    title: str = Field(default="Generated Examination Paper", description="Title of the question paper")
    subject: Optional[str] = Field(default=None, description="Subject (e.g. Physics, Mathematics, Computer Science)")
    target_grade: Optional[str] = Field(default=None, description="Target Grade / Academic Level (e.g., Grade 10, University)")
    difficulty_level: DifficultyLevel = Field(
        default=DifficultyLevel.MEDIUM, description="Overall difficulty (easy, medium, hard, mixed)"
    )
    total_marks: int = Field(default=50, ge=1, le=500, description="Target total marks")
    distribution: Optional[QuestionTypesDistribution] = Field(
        default_factory=QuestionTypesDistribution,
        description="Desired question type count distribution",
    )
    custom_instructions: Optional[str] = Field(
        default=None, description="Extra instructions for question style or specific topics to focus on"
    )
    model: Optional[str] = Field(
        default=None, description="Ollama model to use (defaults to configured Gemma model)"
    )


class QuestionSchema(BaseModel):
    question_number: int
    question_text: str
    question_type: QuestionType
    difficulty: DifficultyLevel
    options: Optional[Dict[str, str]] = None  # e.g. {"A": "...", "B": "...", "C": "...", "D": "..."}
    correct_answer: str
    explanation: Optional[str] = None
    marks: int = 1
    formula_latex: Optional[str] = None
    image_reference: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class QuestionPaperResponse(BaseModel):
    id: int
    document_id: Optional[int]
    title: str
    subject: Optional[str]
    target_grade: Optional[str]
    difficulty_level: DifficultyLevel
    total_marks: int
    total_questions: int
    status: PaperStatus
    error_message: Optional[str] = None
    created_at: datetime
    questions: List[QuestionSchema] = []

    model_config = ConfigDict(from_attributes=True)


class QuestionPaperSummary(BaseModel):
    id: int
    document_id: Optional[int]
    title: str
    subject: Optional[str]
    difficulty_level: DifficultyLevel
    total_marks: int
    total_questions: int
    status: PaperStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
