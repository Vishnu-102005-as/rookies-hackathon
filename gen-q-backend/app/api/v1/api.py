from fastapi import APIRouter
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.ollama import router as ollama_router
from app.api.v1.endpoints.questions import router as questions_router

api_router = APIRouter()
api_router.include_router(ollama_router)
api_router.include_router(documents_router)
api_router.include_router(questions_router)
