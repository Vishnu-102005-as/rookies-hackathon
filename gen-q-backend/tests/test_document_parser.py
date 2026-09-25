import tempfile
from pathlib import Path
import docx
import pytest
from app.services.document_parser import document_parser_service


def test_parse_text_with_formulas():
    sample_text = """
    # Physics Examination Chapter 1
    The energy-mass equivalence is given by $E = mc^2$.
    The quadratic formula is $$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$.
    Newton's second law is F = ma.
    Calculate the velocity given distance s and time t.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(sample_text)
        temp_path = Path(f.name)

    try:
        result = document_parser_service.parse_file(temp_path)
        assert result.word_count > 0
        assert len(result.formulas) >= 2
        # Check that E = mc^2 or quadratic formula was captured
        formulas_text = [f.latex for f in result.formulas]
        assert any("E = mc^2" in f or "E=mc^2" in f for f in formulas_text)
        assert any("frac" in f for f in formulas_text)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_parse_docx_file():
    doc = docx.Document()
    doc.add_heading("Mathematics Test", level=1)
    doc.add_paragraph("Solve for x: $x^2 + 5x + 6 = 0$.")
    doc.add_paragraph("The area of a circle is $A = \\pi r^2$.")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        temp_path = Path(f.name)

    try:
        doc.save(str(temp_path))
        result = document_parser_service.parse_file(temp_path)

        assert "Mathematics Test" in result.full_text
        assert result.word_count > 0
        assert len(result.formulas) >= 1
    finally:
        if temp_path.exists():
            temp_path.unlink()
