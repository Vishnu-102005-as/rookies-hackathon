from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
import httpx

from app.main import app
from app.schemas.ollama import ChatMessage, ChatRequest, GenerateRequest, MessageRole
from app.services.ollama_service import OllamaService, OllamaServiceException

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "health_check" in data
    assert "default_model" in data


@pytest.mark.asyncio
async def test_service_generate_success():
    service = OllamaService(base_url="http://localhost:11434", default_model="gemma2")

    mock_response = httpx.Response(
        status_code=200,
        json={
            "model": "gemma2",
            "response": "Hello! How can I help you?",
            "done": True,
            "total_duration": 1200000,
            "eval_count": 8,
        },
        request=httpx.Request("POST", "http://localhost:11434/api/generate"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        req = GenerateRequest(prompt="Hello")
        result = await service.generate(req)

        assert result.response == "Hello! How can I help you?"
        assert result.model == "gemma2"
        assert result.done is True


@pytest.mark.asyncio
async def test_service_chat_success():
    service = OllamaService(base_url="http://localhost:11434", default_model="gemma2")

    mock_response = httpx.Response(
        status_code=200,
        json={
            "model": "gemma2",
            "message": {
                "role": "assistant",
                "content": "Gemma is running locally.",
            },
            "done": True,
        },
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        req = ChatRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="Are you running?")]
        )
        result = await service.chat(req)

        assert result.message.content == "Gemma is running locally."
        assert result.message.role == MessageRole.ASSISTANT


@pytest.mark.asyncio
async def test_service_connection_error():
    service = OllamaService(base_url="http://localhost:11434", default_model="gemma2")

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        req = GenerateRequest(prompt="Hi")
        with pytest.raises(OllamaServiceException) as exc_info:
            await service.generate(req)
        assert exc_info.value.status_code == 503
