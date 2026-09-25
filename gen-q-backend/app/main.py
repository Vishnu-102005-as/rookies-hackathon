from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: attempt to initialize DB tables if DB is reachable
    try:
        await init_db()
        logger.info("Database tables initialized or verified.")
    except Exception as e:
        logger.warning(
            f"Database auto-initialization skipped or failed ({e}). "
            "Ensure PostgreSQL is running and credentials in .env are correct."
        )
    yield
    # Shutdown: clean up if needed


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for uploaded files and extracted images
upload_dir = settings.upload_path
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "message": f"{settings.PROJECT_NAME} is running",
        "docs": "/docs",
        "health_check": f"{settings.API_V1_STR}/ollama/health",
        "default_model": settings.OLLAMA_DEFAULT_MODEL,
        "database": "PostgreSQL (genq_db)",
    }
