"""Tests for application settings and configuration."""

import pytest
from app.config import Settings


def test_settings_load_defaults():
    """Verify settings can be instantiated with defaults."""
    settings = Settings(
        google_api_key="test-key",
        llm_model="gemini-2.5-flash",
        embedding_provider="gemini",
        gemini_embedding_model="gemini-embedding-001",
        local_embedding_model="all-MiniLM-L6-v2",
        target_repo_path="./demo_repo",
        chroma_dir="./chroma_db",
        max_agent_steps=12,
    )
    assert settings.llm_model == "gemini-2.5-flash"
    assert settings.embedding_provider == "gemini"
    assert settings.gemini_embedding_model == "gemini-embedding-001"
    assert settings.local_embedding_model == "all-MiniLM-L6-v2"
    assert settings.target_repo_path == "./demo_repo"
    assert settings.chroma_dir == "./chroma_db"
    assert settings.max_agent_steps == 12


def test_require_google_api_key_success():
    """Verify require_google_api_key returns key when present."""
    settings = Settings(google_api_key="valid-secret-key")
    assert settings.require_google_api_key() == "valid-secret-key"


def test_require_google_api_key_missing_raises():
    """Verify require_google_api_key raises friendly ValueError when key is missing."""
    settings = Settings(google_api_key="")
    with pytest.raises(ValueError, match="GOOGLE_API_KEY is missing or empty"):
        settings.require_google_api_key()

    settings_none = Settings(google_api_key=None)
    with pytest.raises(ValueError, match="GOOGLE_API_KEY is missing or empty"):
        settings_none.require_google_api_key()


def test_embedding_provider_normalization():
    """Verify embedding provider string is stripped and lowercased."""
    settings_gemini = Settings(embedding_provider="  GEMINI  ")
    assert settings_gemini.embedding_provider == "gemini"

    settings_local = Settings(embedding_provider="Local")
    assert settings_local.embedding_provider == "local"
