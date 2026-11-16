"""Configuration settings for BugSleuth using pydantic-settings."""

from functools import lru_cache
from typing import Literal, Optional
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.logging_setup import get_logger

logger = get_logger("config")


class Settings(BaseSettings):
    """BugSleuth application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        description="Google Gemini API Key",
    )
    llm_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias=AliasChoices("LLM_MODEL"),
        description="Gemini LLM model name",
    )
    embedding_provider: Literal["gemini", "local"] = Field(
        default="gemini",
        validation_alias=AliasChoices("EMBEDDING_PROVIDER"),
        description="Embedding provider to use ('gemini' or 'local')",
    )
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001",
        validation_alias=AliasChoices("GEMINI_EMBEDDING_MODEL"),
        description="Gemini embedding model name",
    )
    local_embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        validation_alias=AliasChoices("LOCAL_EMBEDDING_MODEL"),
        description="HuggingFace local embedding model name",
    )
    target_repo_path: str = Field(
        default="./demo_repo",
        validation_alias=AliasChoices("TARGET_REPO_PATH"),
        description="Path to target repository to analyze",
    )
    chroma_dir: str = Field(
        default="./chroma_db",
        validation_alias=AliasChoices("CHROMA_DIR"),
        description="Chroma vector database persistence directory",
    )
    max_agent_steps: int = Field(
        default=12,
        validation_alias=AliasChoices("MAX_AGENT_STEPS"),
        description="Maximum reasoning steps for the agent loop",
    )

    @field_validator("embedding_provider", mode="before")
    @classmethod
    def normalize_provider(cls, v: str) -> str:
        """Normalize embedding provider string."""
        if isinstance(v, str):
            val = v.strip().lower()
            if val in ("gemini", "local"):
                return val
        return v

    def require_google_api_key(self) -> str:
        """Validate and return GOOGLE_API_KEY.

        Raises:
            ValueError: Friendly message if GOOGLE_API_KEY is missing or empty.
        """
        if not self.google_api_key or not self.google_api_key.strip():
            msg = (
                "GOOGLE_API_KEY is missing or empty. "
                "Please configure GOOGLE_API_KEY in your .env file or environment variables "
                "to interact with Google Gemini models."
            )
            logger.error(msg)
            raise ValueError(msg)
        return self.google_api_key.strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()
