import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.models.question_paper import DifficultyLevel, QuestionType
from app.schemas.document import ParsedDocumentResult
from app.schemas.ollama import GenerateRequest, GenerationOptions
from app.schemas.question_paper import (
    GenerateQuestionPaperRequest,
    QuestionSchema,
    QuestionTypesDistribution,
)
from app.services.ollama_service import OllamaServiceException, ollama_service

logger = logging.getLogger(__name__)


class QuestionGeneratorService:
    def __init__(self):
        self.ollama = ollama_service

    def _build_prompt(
        self,
        request: GenerateQuestionPaperRequest,
        context_text: str,
        formulas: Optional[List[Dict[str, Any]]] = None,
        images: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Construct a structured prompt for Gemma to generate the question paper."""
        dist: QuestionTypesDistribution = request.distribution or QuestionTypesDistribution()

        # Build formulas summary if available
        formula_context = ""
        if formulas:
            extracted_math = [f.get("latex", "") for f in formulas[:15] if f.get("latex")]
            if extracted_math:
                formula_context = (
                    f"\nDetected Key Formulas/Equations in Source Material:\n"
                    + "\n".join(f"- ${eq}$" for eq in extracted_math)
                    + "\n"
                )

        image_context = ""
        if images:
            img_captions = [f"Image {i+1}: {img.get('caption', 'Diagram')}" for i, img in enumerate(images[:5])]
            if img_captions:
                image_context = f"\nDetected Diagrams/Figures in Source Material:\n" + "\n".join(f"- {c}" for c in img_captions) + "\n"

        prompt = f"""You are an expert academic examiner and curriculum specialist.
Your task is to generate a comprehensive, high-quality examination question paper based strictly on the provided source material.

### Exam Requirements:
- Title: {request.title}
- Subject: {request.subject or 'Academic Subject'}
- Academic / Target Grade Level: {request.target_grade or 'Standard'}
- Target Difficulty Level: {request.difficulty_level.value.upper()}
- Total Marks Target: {request.total_marks}

### Required Question Types Breakdown:
- Multiple Choice Questions (MCQ): {dist.mcq or 0} questions (4 options: A, B, C, D)
- Short Answer Questions: {dist.short_answer or 0} questions
- Long / Descriptive Questions: {dist.long_answer or 0} questions
- Formula / Calculation Questions: {dist.formula_based or 0} questions (must test mathematical or conceptual derivation)
- True / False Questions: {dist.true_false or 0} questions

{f'### Special User Instructions:\n{request.custom_instructions}\n' if request.custom_instructions else ''}
{formula_context}
{image_context}
### Source Material:
{context_text[:8000]}

### Output Format Instructions:
You MUST respond with a valid, raw JSON object (and nothing else). Do not include markdown preamble.
The JSON object must follow this exact structure:
{{
  "title": "{request.title}",
  "total_marks": {request.total_marks},
  "questions": [
    {{
      "question_number": 1,
      "question_text": "Detailed question text here",
      "question_type": "mcq",
      "difficulty": "{request.difficulty_level.value if request.difficulty_level.value != 'mixed' else 'easy'}",
      "options": {{
        "A": "First option",
        "B": "Second option",
        "C": "Third option",
        "D": "Fourth option"
      }},
      "correct_answer": "A",
      "explanation": "Clear step-by-step reasoning or formula derivation",
      "marks": 1,
      "formula_latex": "Optional LaTeX equation if applicable"
    }},
    {{
      "question_number": 2,
      "question_text": "Describe the core principles of ...",
      "question_type": "short_answer",
      "difficulty": "medium",
      "options": null,
      "correct_answer": "Key points expected in the answer",
      "explanation": "Grading rubric and expected key terms",
      "marks": 3,
      "formula_latex": null
    }}
  ]
}}
Ensure question_type is one of: "mcq", "short_answer", "long_answer", "true_false", "formula_based".
Ensure difficulty is one of: "easy", "medium", "hard".
"""
        return prompt

    def _parse_llm_json_response(self, raw_response: str) -> List[QuestionSchema]:
        """Extract and validate questions list from Gemma's response."""
        clean_text = raw_response.strip()

        # Remove markdown code fences if present
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text)
            clean_text = clean_text.strip()

        # Find first '{' or '[' and last '}' or ']'
        start_idx = clean_text.find("{")
        end_idx = clean_text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            clean_text = clean_text[start_idx : end_idx + 1]

        data = json.loads(clean_text)

        questions_raw = []
        if isinstance(data, dict):
            questions_raw = data.get("questions", [])
        elif isinstance(data, list):
            questions_raw = data

        parsed_questions: List[QuestionSchema] = []
        for idx, q in enumerate(questions_raw, start=1):
            try:
                # Normalize question type
                raw_type = str(q.get("question_type", "short_answer")).lower()
                valid_types = {t.value: t for t in QuestionType}
                q_type = valid_types.get(raw_type, QuestionType.SHORT_ANSWER)

                # Normalize difficulty
                raw_diff = str(q.get("difficulty", "medium")).lower()
                valid_diffs = {d.value: d for d in DifficultyLevel if d != DifficultyLevel.MIXED}
                q_diff = valid_diffs.get(raw_diff, DifficultyLevel.MEDIUM)

                options = q.get("options")
                if options and not isinstance(options, dict):
                    options = None

                parsed_questions.append(
                    QuestionSchema(
                        question_number=q.get("question_number", idx),
                        question_text=q.get("question_text", f"Question {idx}"),
                        question_type=q_type,
                        difficulty=q_diff,
                        options=options,
                        correct_answer=str(q.get("correct_answer", "")),
                        explanation=q.get("explanation"),
                        marks=int(q.get("marks", 1)),
                        formula_latex=q.get("formula_latex"),
                        image_reference=q.get("image_reference"),
                    )
                )
            except Exception as item_err:
                logger.warning(f"Skipping malformed question item #{idx}: {item_err}")
                continue

        return parsed_questions

    async def generate_questions_from_context(
        self,
        request: GenerateQuestionPaperRequest,
        context_text: str,
        formulas: Optional[List[Dict[str, Any]]] = None,
        images: Optional[List[Dict[str, Any]]] = None,
    ) -> List[QuestionSchema]:
        """Send prompt to Ollama Gemma and parse the generated questions."""
        prompt = self._build_prompt(request, context_text, formulas, images)

        system_instruction = (
            "You are a rigorous exam creation engine. Return only strict, valid JSON matching the requested schema."
        )

        llm_request = GenerateRequest(
            prompt=prompt,
            model=request.model,
            system=system_instruction,
            format="json",
            options=GenerationOptions(
                temperature=0.4,  # Lower temperature for higher structure consistency
                top_p=0.9,
                num_predict=4096,
            ),
        )

        response = await self.ollama.generate(llm_request)
        questions = self._parse_llm_json_response(response.response)

        if not questions:
            raise OllamaServiceException(
                message="Gemma model generated an empty or non-parseable question list. Please try again with adjusted parameters.",
                status_code=502,
            )

        return questions


# Singleton instance
question_generator_service = QuestionGeneratorService()
