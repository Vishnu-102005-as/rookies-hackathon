from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.document import FileType


class ExtractedFormula(BaseModel):
    latex: str = Field(..., description="LaTeX representation of the formula/equation")
    raw_text: Optional[str] = Field(default=None, description="Raw detected formula or context")
    page: Optional[int] = Field(default=None, description="Page number where found")
    position_index: Optional[int] = Field(default=None, description="Order index in document")


class ExtractedImage(BaseModel):
    filename: str = Field(..., description="Saved image file name")
    file_path: str = Field(..., description="Server relative or absolute path to saved image")
    format: str = Field(default="png", description="Image format e.g. png, jpeg")
    page: Optional[int] = Field(default=None, description="Page number where image was embedded")
    caption: Optional[str] = Field(default=None, description="Caption or surrounding context text")


class ParsedDocumentResult(BaseModel):
    full_text: str
    formulas: List[ExtractedFormula] = []
    images: List[ExtractedImage] = []
    word_count: int = 0
    total_formulas: int = 0
    total_images: int = 0
    metadata: Dict[str, Any] = {}


class DocumentRead(BaseModel):
    id: int
    filename: str
    file_type: FileType
    file_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentExtractRead(BaseModel):
    id: int
    document_id: int
    raw_text: str
    formulas: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    summary: Optional[str] = None
    total_words: int
    total_formulas: int
    total_images: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailRead(DocumentRead):
    extract: Optional[DocumentExtractRead] = None
