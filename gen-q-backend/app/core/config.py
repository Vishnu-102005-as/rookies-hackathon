from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "Gen-Q Backend API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

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


settings = Settings()
