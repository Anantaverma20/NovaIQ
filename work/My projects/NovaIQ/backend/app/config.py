"""
Single source of truth for application configuration.
All settings are typed and loaded from environment variables.
"""
from functools import lru_cache
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with graceful degradation.
    
    - If OPENAI_API_KEY is missing, vector operations are disabled
    - All settings have sensible defaults for local development
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )
    
    # === API Configuration ===
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="CORS allowed origins"
    )
    
    # === Database ===
    DATABASE_URL: str = Field(
        default="sqlite:///./data/novaiq.db",
        description="SQLite database path"
    )
    
    # === OpenAI (optional for embeddings) ===
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key for embeddings (optional)"
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model for text generation"
    )
    OPENAI_EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model"
    )
    
    # === Vector Store (optional) ===
    CHROMA_PERSIST_DIR: str = Field(
        default="./data/chroma",
        description="ChromaDB persistence directory"
    )
    ENABLE_VECTORS: bool = Field(
        default=True,
        description="Enable vector operations (auto-disabled if no OpenAI key)"
    )
    
    # === External Search API ===
    SEARCH_API_KEY: Optional[str] = Field(
        default=None,
        description="Search API key (You.com, Brave, etc.)"
    )
    SEARCH_API_BASE_URL: str = Field(
        default="https://api.you.com",
        description="Search API base URL"
    )
    
    # === Ingestion Configuration ===
    INGESTION_QUERY: str = Field(
        default="AI research breakthrough",
        description="Default search query for ingestion"
    )
    INGESTION_MAX_RESULTS: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Max results per ingestion run"
    )
    INGESTION_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description="Secret token for webhook-triggered ingestion"
    )
    
    # === Rate Limiting ===
    RATE_LIMIT_REQUESTS: int = Field(
        default=100,
        ge=1,
        description="Max requests per window"
    )
    RATE_LIMIT_WINDOW_SECONDS: int = Field(
        default=60,
        ge=1,
        description="Rate limit window in seconds"
    )
    
    # === Retry Configuration ===
    HTTP_RETRY_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    HTTP_RETRY_WAIT_MIN_SECONDS: float = Field(default=1.0, ge=0.1)
    HTTP_RETRY_WAIT_MAX_SECONDS: float = Field(default=10.0, ge=0.1)
    
    @field_validator("ENABLE_VECTORS")
    @classmethod
    def disable_vectors_without_openai_key(cls, v: bool, info) -> bool:
        """Auto-disable vectors if OpenAI API key is not provided."""
        openai_key = info.data.get("OPENAI_API_KEY")
        if v and not openai_key:
            return False
        return v
    
    @property
    def vectors_enabled(self) -> bool:
        """Check if vector operations are available."""
        return self.ENABLE_VECTORS and self.OPENAI_API_KEY is not None
    
    @property
    def search_api_available(self) -> bool:
        """Check if external search API is configured."""
        return self.SEARCH_API_KEY is not None


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    This is the single entry point for all configuration.
    The LRU cache ensures we only parse env vars once.
    """
    return Settings()


def reload_settings() -> Settings:
    """
    Force reload settings from environment.
    Useful for testing or when env vars change at runtime.
    """
    get_settings.cache_clear()
    return get_settings()

