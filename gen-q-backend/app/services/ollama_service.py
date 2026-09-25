import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx

from app.core.config import settings
from app.schemas.ollama import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    GenerateRequest,
    GenerateResponse,
    GenerationOptions,
    MessageRole,
    ModelInfo,
    OllamaHealthResponse,
)

logger = logging.getLogger(__name__)


class OllamaServiceException(Exception):
    """Base exception for Ollama service operations."""

    def __init__(self, message: str, status_code: int = 500, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class OllamaService:
    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.default_model = default_model or settings.OLLAMA_DEFAULT_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout, connect=10.0),
        )

    def _prepare_options(self, options: Optional[Union[GenerationOptions, Dict[str, Any]]]) -> Dict[str, Any]:
        if options is None:
            return {}
        if isinstance(options, GenerationOptions):
            return options.model_dump(exclude_none=True)
        return options

    async def check_health(self) -> OllamaHealthResponse:
        """Check connection to the local Ollama instance and list available models."""
        try:
            async with self._get_client() as client:
                response = await client.get("/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    return OllamaHealthResponse(
                        status="healthy",
                        base_url=self.base_url,
                        default_model=self.default_model,
                        is_connected=True,
                        available_models=models,
                    )
                return OllamaHealthResponse(
                    status="unhealthy",
                    base_url=self.base_url,
                    default_model=self.default_model,
                    is_connected=False,
                    error=f"Ollama returned HTTP status {response.status_code}",
                )
        except httpx.ConnectError:
            return OllamaHealthResponse(
                status="offline",
                base_url=self.base_url,
                default_model=self.default_model,
                is_connected=False,
                error=(
                    f"Could not connect to Ollama at {self.base_url}. "
                    "Make sure Ollama is installed and running (`ollama serve`)."
                ),
            )
        except Exception as e:
            return OllamaHealthResponse(
                status="error",
                base_url=self.base_url,
                default_model=self.default_model,
                is_connected=False,
                error=str(e),
            )

    async def list_models(self) -> List[ModelInfo]:
        """Fetch list of models available in the local Ollama instance."""
        try:
            async with self._get_client() as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                data = response.json()
                models_data = data.get("models", [])
                return [ModelInfo(**m) for m in models_data]
        except httpx.ConnectError:
            raise OllamaServiceException(
                message=f"Cannot connect to Ollama at {self.base_url}. Ensure Ollama is running.",
                status_code=503,
            )
        except Exception as e:
            logger.error(f"Error listing Ollama models: {e}")
            raise OllamaServiceException(message=str(e), status_code=500)

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Generate a completion for a prompt using Gemma/Ollama (non-streaming)."""
        model = request.model or self.default_model
        payload = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
            "options": self._prepare_options(request.options),
        }
        if request.system:
            payload["system"] = request.system
        if request.format:
            payload["format"] = request.format
        if request.raw:
            payload["raw"] = request.raw

        try:
            async with self._get_client() as client:
                response = await client.post("/api/generate", json=payload)
                if response.status_code == 404:
                    raise OllamaServiceException(
                        message=f"Model '{model}' not found in local Ollama. Run `ollama pull {model}` to download it.",
                        status_code=404,
                    )
                response.raise_for_status()
                data = response.json()
                return GenerateResponse(
                    model=data.get("model", model),
                    response=data.get("response", ""),
                    done=data.get("done", True),
                    context=data.get("context"),
                    total_duration=data.get("total_duration"),
                    prompt_eval_count=data.get("prompt_eval_count"),
                    eval_count=data.get("eval_count"),
                )
        except httpx.ConnectError:
            raise OllamaServiceException(
                message=f"Cannot connect to Ollama at {self.base_url}. Ensure Ollama is running (`ollama serve`).",
                status_code=503,
            )
        except httpx.TimeoutException:
            raise OllamaServiceException(
                message=f"Ollama generation request timed out after {self.timeout}s.",
                status_code=504,
            )
        except OllamaServiceException:
            raise
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise OllamaServiceException(message=str(e), status_code=500)

    async def generate_stream(self, request: GenerateRequest) -> AsyncGenerator[str, None]:
        """Stream token-by-token generation for a prompt using Gemma/Ollama."""
        model = request.model or self.default_model
        payload = {
            "model": model,
            "prompt": request.prompt,
            "stream": True,
            "options": self._prepare_options(request.options),
        }
        if request.system:
            payload["system"] = request.system
        if request.format:
            payload["format"] = request.format
        if request.raw:
            payload["raw"] = request.raw

        try:
            async with self._get_client() as client:
                async with client.stream("POST", "/api/generate", json=payload) as response:
                    if response.status_code == 404:
                        raise OllamaServiceException(
                            message=f"Model '{model}' not found in local Ollama. Run `ollama pull {model}`.",
                            status_code=404,
                        )
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        yield chunk.get("response", "")
                        if chunk.get("done", False):
                            break
        except httpx.ConnectError:
            raise OllamaServiceException(
                message=f"Cannot connect to Ollama at {self.base_url}. Ensure Ollama is running (`ollama serve`).",
                status_code=503,
            )
        except OllamaServiceException:
            raise
        except Exception as e:
            logger.error(f"Ollama stream generation failed: {e}")
            raise OllamaServiceException(message=str(e), status_code=500)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a multi-turn conversation to Gemma/Ollama (non-streaming)."""
        model = request.model or self.default_model
        messages_payload = [
            {"role": m.role.value if isinstance(m.role, MessageRole) else m.role, "content": m.content}
            for m in request.messages
        ]
        payload = {
            "model": model,
            "messages": messages_payload,
            "stream": False,
            "options": self._prepare_options(request.options),
        }
        if request.format:
            payload["format"] = request.format

        try:
            async with self._get_client() as client:
                response = await client.post("/api/chat", json=payload)
                if response.status_code == 404:
                    raise OllamaServiceException(
                        message=f"Model '{model}' not found in local Ollama. Run `ollama pull {model}` to download it.",
                        status_code=404,
                    )
                response.raise_for_status()
                data = response.json()
                msg = data.get("message", {})
                return ChatResponse(
                    model=data.get("model", model),
                    message=ChatMessage(
                        role=msg.get("role", MessageRole.ASSISTANT),
                        content=msg.get("content", ""),
                    ),
                    done=data.get("done", True),
                    total_duration=data.get("total_duration"),
                    prompt_eval_count=data.get("prompt_eval_count"),
                    eval_count=data.get("eval_count"),
                )
        except httpx.ConnectError:
            raise OllamaServiceException(
                message=f"Cannot connect to Ollama at {self.base_url}. Ensure Ollama is running (`ollama serve`).",
                status_code=503,
            )
        except httpx.TimeoutException:
            raise OllamaServiceException(
                message=f"Ollama chat request timed out after {self.timeout}s.",
                status_code=504,
            )
        except OllamaServiceException:
            raise
        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
            raise OllamaServiceException(message=str(e), status_code=500)

    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Stream multi-turn chat tokens from Gemma/Ollama."""
        model = request.model or self.default_model
        messages_payload = [
            {"role": m.role.value if isinstance(m.role, MessageRole) else m.role, "content": m.content}
            for m in request.messages
        ]
        payload = {
            "model": model,
            "messages": messages_payload,
            "stream": True,
            "options": self._prepare_options(request.options),
        }
        if request.format:
            payload["format"] = request.format

        try:
            async with self._get_client() as client:
                async with client.stream("POST", "/api/chat", json=payload) as response:
                    if response.status_code == 404:
                        raise OllamaServiceException(
                            message=f"Model '{model}' not found in local Ollama. Run `ollama pull {model}`.",
                            status_code=404,
                        )
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        msg_chunk = chunk.get("message", {}).get("content", "")
                        yield msg_chunk
                        if chunk.get("done", False):
                            break
        except httpx.ConnectError:
            raise OllamaServiceException(
                message=f"Cannot connect to Ollama at {self.base_url}. Ensure Ollama is running (`ollama serve`).",
                status_code=503,
            )
        except OllamaServiceException:
            raise
        except Exception as e:
            logger.error(f"Ollama stream chat failed: {e}")
            raise OllamaServiceException(message=str(e), status_code=500)

    async def embed(self, prompt: str, model: Optional[str] = None) -> List[float]:
        """Generate vector embeddings for a given prompt using Ollama."""
        model = model or self.default_model
        payload = {"model": model, "prompt": prompt}
        try:
            async with self._get_client() as client:
                response = await client.post("/api/embeddings", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("embedding", [])
        except httpx.ConnectError:
            raise OllamaServiceException(
                message=f"Cannot connect to Ollama at {self.base_url}.",
                status_code=503,
            )
        except Exception as e:
            logger.error(f"Ollama embeddings generation failed: {e}")
            raise OllamaServiceException(message=str(e), status_code=500)


# Default singleton instance
ollama_service = OllamaService()
