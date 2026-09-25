import io
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid

import docx
from PIL import Image
from pypdf import PdfReader

from app.core.config import settings
from app.schemas.document import ExtractedFormula, ExtractedImage, ParsedDocumentResult

# Regex patterns for formulas and LaTeX expressions
FORMULA_PATTERNS = [
    # Block Math: $$...$$ or \[...\]
    re.compile(r"\$\$(.+?)\$\$", re.DOTALL),
    re.compile(r"\\\[(.+?)\\\]", re.DOTALL),
    # LaTeX environments
    re.compile(r"\\begin\{(?:equation|align|gather|matrix|pmatrix|bmatrix)\*?\}(.+?)\\end\{(?:equation|align|gather|matrix|pmatrix|bmatrix)\*?\}", re.DOTALL),
    # Inline Math: $...$ or \(...\)
    re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)", re.DOTALL),
    re.compile(r"\\\((.+?)\\\)", re.DOTALL),
    # Common math patterns with math symbols (LaTeX keywords or equations)
    re.compile(r"(?:\\frac\{[^}]+\}\{[^}]+\}|\\sqrt\{[^}]+\}|\\sum_\{[^}]+\}|\\int_\{[^}]+\}|\\prod_\{[^}]+\}|\\partial|\\nabla|\\alpha|\\beta|\\gamma|\\delta|\\theta|\\pi|\\lambda|\\sigma|\\omega)", re.IGNORECASE),
    # Plain algebraic equations: e.g. E = mc^2, y = mx + c, a^2 + b^2 = c^2
    re.compile(r"\b[A-Za-z]\s*=\s*[-+]?[0-9A-Za-z\s\+\-\*\/\^\(\)]+[0-9A-Za-z\)]\b"),
]


class DocumentParserService:
    def __init__(self, base_upload_dir: Optional[Path] = None):
        self.base_upload_dir = base_upload_dir or settings.upload_path

    def _extract_formulas_from_text(self, text: str, page: Optional[int] = None) -> List[ExtractedFormula]:
        """Extract LaTeX and standard mathematical formulas from text."""
        formulas: List[ExtractedFormula] = []
        seen_formulas = set()
        pos_idx = 0

        for pattern in FORMULA_PATTERNS:
            for match in pattern.finditer(text):
                matched_str = match.group(0).strip()
                # Clean delimiters if needed
                clean_latex = matched_str
                if clean_latex.startswith("$$") and clean_latex.endswith("$$"):
                    clean_latex = clean_latex[2:-2].strip()
                elif clean_latex.startswith("$") and clean_latex.endswith("$"):
                    clean_latex = clean_latex[1:-1].strip()
                elif clean_latex.startswith("\\[") and clean_latex.endswith("\\]"):
                    clean_latex = clean_latex[2:-2].strip()
                elif clean_latex.startswith("\\(") and clean_latex.endswith("\\)"):
                    clean_latex = clean_latex[2:-2].strip()

                if len(clean_latex) > 1 and clean_latex not in seen_formulas:
                    seen_formulas.add(clean_latex)
                    # Context snippet around the formula
                    start = max(0, match.start() - 40)
                    end = min(len(text), match.end() + 40)
                    context_snippet = text[start:end].replace("\n", " ").strip()

                    formulas.append(
                        ExtractedFormula(
                            latex=clean_latex,
                            raw_text=context_snippet,
                            page=page,
                            position_index=pos_idx,
                        )
                    )
                    pos_idx += 1

        return formulas

    def parse_pdf(self, file_path: Path, image_output_dir: Path) -> ParsedDocumentResult:
        """Parse PDF document and separate text, math formulas, and images."""
        reader = PdfReader(str(file_path))
        full_text_pages: List[str] = []
        all_formulas: List[ExtractedFormula] = []
        all_images: List[ExtractedImage] = []

        image_output_dir.mkdir(parents=True, exist_ok=True)

        for page_idx, page in enumerate(reader.pages, start=1):
            # 1. Extract text
            page_text = page.extract_text() or ""
            if page_text.strip():
                full_text_pages.append(page_text)
                # 2. Extract formulas from page text
                page_formulas = self._extract_formulas_from_text(page_text, page=page_idx)
                all_formulas.extend(page_formulas)

            # 3. Extract embedded images
            try:
                for img_idx, img_file in enumerate(page.images, start=1):
                    ext = Path(img_file.name).suffix.lower().lstrip(".") or "png"
                    img_filename = f"pdf_p{page_idx}_img{img_idx}_{uuid.uuid4().hex[:6]}.{ext}"
                    dest_path = image_output_dir / img_filename

                    with open(dest_path, "wb") as f:
                        f.write(img_file.data)

                    # Compute relative web path
                    rel_path = str(dest_path.relative_to(self.base_upload_dir.parent)).replace("\\", "/")

                    all_images.append(
                        ExtractedImage(
                            filename=img_filename,
                            file_path=rel_path,
                            format=ext,
                            page=page_idx,
                            caption=f"Image from page {page_idx}",
                        )
                    )
            except Exception:
                pass  # Graceful fallback if image extraction on a page encounters unsupported compression

        full_text = "\n\n".join(full_text_pages)
        words = len(full_text.split())

        return ParsedDocumentResult(
            full_text=full_text,
            formulas=all_formulas,
            images=all_images,
            word_count=words,
            total_formulas=len(all_formulas),
            total_images=len(all_images),
            metadata={"pages": len(reader.pages), "type": "pdf"},
        )

    def parse_docx(self, file_path: Path, image_output_dir: Path) -> ParsedDocumentResult:
        """Parse Word (.docx) document and separate text, math formulas, and images."""
        doc = docx.Document(str(file_path))
        full_text_paragraphs: List[str] = []
        all_formulas: List[ExtractedFormula] = []
        all_images: List[ExtractedImage] = []

        image_output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Extract paragraphs and Office Math (OMML) / LaTeX
        for para_idx, para in enumerate(doc.paragraphs, start=1):
            text = para.text
            if text.strip():
                full_text_paragraphs.append(text)
                formulas = self._extract_formulas_from_text(text)
                all_formulas.extend(formulas)

            # Inspect raw XML for Office Math elements (m:oMath / m:oMathPara)
            xml_str = para._element.xml
            if "m:oMath" in xml_str:
                math_text_matches = re.findall(r"<m:t[^>]*>(.*?)</m:t>", xml_str)
                if math_text_matches:
                    omml_math = " ".join(math_text_matches)
                    if omml_math.strip() and not any(f.latex == omml_math.strip() for f in all_formulas):
                        all_formulas.append(
                            ExtractedFormula(
                                latex=omml_math.strip(),
                                raw_text=text[:100] if text else "Word Office Math element",
                                position_index=len(all_formulas),
                            )
                        )

        # 2. Extract tables content
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    full_text_paragraphs.append(row_text)

        # 3. Extract embedded images from document package parts
        for rel_id, rel in doc.part.rels.items():
            if "image" in rel.target_ref:
                try:
                    img_part = rel.target_part
                    img_bytes = img_part.blob
                    ext = Path(img_part.partname).suffix.lower().lstrip(".") or "png"
                    img_filename = f"docx_img_{uuid.uuid4().hex[:8]}.{ext}"
                    dest_path = image_output_dir / img_filename

                    with open(dest_path, "wb") as f:
                        f.write(img_bytes)

                    rel_path = str(dest_path.relative_to(self.base_upload_dir.parent)).replace("\\", "/")

                    all_images.append(
                        ExtractedImage(
                            filename=img_filename,
                            file_path=rel_path,
                            format=ext,
                            caption="Embedded image from Word document",
                        )
                    )
                except Exception:
                    pass

        full_text = "\n\n".join(full_text_paragraphs)
        words = len(full_text.split())

        return ParsedDocumentResult(
            full_text=full_text,
            formulas=all_formulas,
            images=all_images,
            word_count=words,
            total_formulas=len(all_formulas),
            total_images=len(all_images),
            metadata={"paragraphs": len(doc.paragraphs), "tables": len(doc.tables), "type": "docx"},
        )

    def parse_txt_or_md(self, file_path: Path) -> ParsedDocumentResult:
        """Parse plain text or Markdown document."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        formulas = self._extract_formulas_from_text(text)
        words = len(text.split())

        return ParsedDocumentResult(
            full_text=text,
            formulas=formulas,
            images=[],
            word_count=words,
            total_formulas=len(formulas),
            total_images=0,
            metadata={"type": file_path.suffix.lower().lstrip(".")},
        )

    def parse_file(self, file_path: Path) -> ParsedDocumentResult:
        """Universal parser dispatch based on file extension."""
        suffix = file_path.suffix.lower()
        image_dir = self.base_upload_dir / "images" / file_path.stem

        if suffix == ".pdf":
            return self.parse_pdf(file_path, image_dir)
        elif suffix in [".docx", ".doc"]:
            return self.parse_docx(file_path, image_dir)
        elif suffix in [".txt", ".md"]:
            return self.parse_txt_or_md(file_path)
        else:
            # Fallback text parsing
            return self.parse_txt_or_md(file_path)


# Singleton instance
document_parser_service = DocumentParserService()
