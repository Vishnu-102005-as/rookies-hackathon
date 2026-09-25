from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Gen-Q Backend API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/genq_db",
        description="Async PostgreSQL connection URL",
    )
    # File Upload Directory
    UPLOAD_DIR: str = Field(
        default="uploads",
        description="Directory where uploaded documents and extracted assets are stored",
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=25,
        description="Maximum allowed upload size in megabytes",
    )

    # Ollama Local Configuration
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Base URL for the local Ollama instance",
    )
    OLLAMA_DEFAULT_MODEL: str = Field(
        default="gemma2",
        description="Default Gemma model name in Ollama (e.g., gemma2, gemma:2b, gemma:7b, gemma2:2b, gemma2:9b)",
    )
    OLLAMA_TIMEOUT: float = Field(
        default=120.0,
        description="Request timeout for Ollama inference in seconds",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
