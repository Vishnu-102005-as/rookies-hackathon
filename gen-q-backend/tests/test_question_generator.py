import json
from unittest.mock import AsyncMock, patch
import pytest

from app.models.question_paper import DifficultyLevel, QuestionType
from app.schemas.ollama import GenerateResponse
from app.schemas.question_paper import (
    GenerateQuestionPaperRequest,
    QuestionTypesDistribution,
)
from app.services.question_generator import question_generator_service


@pytest.mark.asyncio
async def test_question_generator_success():
    mock_llm_json = {
        "title": "Physics Midterm",
        "total_marks": 10,
        "questions": [
            {
                "question_number": 1,
                "question_text": "What is the speed of light in vacuum?",
                "question_type": "mcq",
                "difficulty": "easy",
                "options": {
                    "A": "3 x 10^8 m/s",
                    "B": "3 x 10^6 m/s",
                    "C": "3 x 10^5 m/s",
                    "D": "3 x 10^7 m/s",
                },
                "correct_answer": "A",
                "explanation": "Standard constant c = 3 x 10^8 m/s.",
                "marks": 2,
                "formula_latex": "c = 3 \\times 10^8 \\text{ m/s}",
            },
            {
                "question_number": 2,
                "question_text": "State Newton's second law of motion.",
                "question_type": "short_answer",
                "difficulty": "medium",
                "options": None,
                "correct_answer": "Force equals mass times acceleration (F = ma).",
                "explanation": "F = dp/dt = ma",
                "marks": 3,
                "formula_latex": "F = ma",
            },
        ],
    }

    mock_response = GenerateResponse(
        model="gemma2",
        response=json.dumps(mock_llm_json),
        done=True,
    )

    with patch("app.services.ollama_service.OllamaService.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response

        request = GenerateQuestionPaperRequest(
            title="Physics Midterm",
            subject="Physics",
            difficulty_level=DifficultyLevel.MEDIUM,
            total_marks=10,
            distribution=QuestionTypesDistribution(mcq=1, short_answer=1),
        )

        questions = await question_generator_service.generate_questions_from_context(
            request=request,
            context_text="Physics content regarding light and Newton's laws.",
            formulas=[{"latex": "F = ma"}],
        )

        assert len(questions) == 2
        assert questions[0].question_type == QuestionType.MCQ
        assert questions[0].options["A"] == "3 x 10^8 m/s"
        assert questions[1].question_type == QuestionType.SHORT_ANSWER
        assert questions[1].formula_latex == "F = ma"
