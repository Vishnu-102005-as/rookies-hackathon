from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: MessageRole = Field(default=MessageRole.USER, description="Role of the message author")
    content: str = Field(..., description="Message text content")
    images: Optional[List[str]] = Field(default=None, description="Optional list of base64-encoded images")


class GenerationOptions(BaseModel):
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(default=0.9, ge=0.0, le=1.0, description="Top-p nucleus sampling")
    top_k: Optional[int] = Field(default=40, ge=0, description="Top-k sampling")
    num_predict: Optional[int] = Field(default=1024, description="Max number of tokens to generate (-1 or -2 for infinite)")
    stop: Optional[List[str]] = Field(default=None, description="Stop tokens to stop generation")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="The prompt string to generate a response for")
    model: Optional[str] = Field(default=None, description="Model name (e.g. gemma2, gemma:2b). Defaults to configured model.")
    system: Optional[str] = Field(default=None, description="System instructions/prompt")
    options: Optional[GenerationOptions] = Field(default_factory=GenerationOptions, description="Model generation parameters")
    format: Optional[str] = Field(default=None, description="Output format (e.g. 'json' for JSON mode)")
    raw: Optional[bool] = Field(default=False, description="Bypass prompt formatting")


class GenerateResponse(BaseModel):
    model: str
    response: str
    done: bool = True
    context: Optional[List[int]] = None
    total_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, description="List of messages in the conversation")
    model: Optional[str] = Field(default=None, description="Model name (e.g. gemma2, gemma:2b). Defaults to configured model.")
    options: Optional[GenerationOptions] = Field(default_factory=GenerationOptions, description="Model generation parameters")
    format: Optional[str] = Field(default=None, description="Output format (e.g. 'json' for JSON mode)")


class ChatResponse(BaseModel):
    model: str
    message: ChatMessage
    done: bool = True
    total_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None


class ModelDetails(BaseModel):
    parent_model: Optional[str] = None
    format: Optional[str] = None
    family: Optional[str] = None
    families: Optional[List[str]] = None
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None


class ModelInfo(BaseModel):
    name: str
    modified_at: Optional[str] = None
    size: Optional[int] = None
    digest: Optional[str] = None
    details: Optional[ModelDetails] = None


class OllamaHealthResponse(BaseModel):
    status: str
    base_url: str
    default_model: str
    is_connected: bool
    available_models: List[str] = []
    error: Optional[str] = None
