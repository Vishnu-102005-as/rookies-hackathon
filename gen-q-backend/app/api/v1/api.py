from fastapi import APIRouter
from app.api.v1.endpoints.ollama import router as ollama_router

api_router = APIRouter()
api_router.include_router(ollama_router)
