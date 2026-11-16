"""LLM and Embeddings factory functions with resilience and retry logic."""

import logging
from typing import Any, List, Optional
from langchain_core.embeddings import Embeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings, get_settings
from app.logging_setup import get_logger

logger = get_logger("llm")


def is_rate_limit_or_quota_error(exc: BaseException) -> bool:
    """Determine whether an exception represents a 429, quota, or transient service error."""
    exc_repr = f"{type(exc).__name__}: {exc}".lower()
    retryable_patterns = [
        "429",
        "resource_exhausted",
        "resourceexhausted",
        "quota",
        "rate limit",
        "too many requests",
        "temporarily unavailable",
        "unavailable",
        "503",
        "timeout",
        "deadline exceeded",
    ]
    is_retryable = any(pattern in exc_repr for pattern in retryable_patterns)
    if is_retryable:
        logger.warning(
            "Detected transient/rate-limit error: %s. Retrying with exponential backoff...",
            exc,
        )
    return is_retryable


def get_retry_decorator(max_attempts: int = 5, min_wait: float = 2.0, max_wait: float = 60.0):
    """Create a tenacity retry decorator configured for LLM/Embeddings calls."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=min_wait, max=max_wait),
        retry=retry_if_exception(is_rate_limit_or_quota_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


llm_retry = get_retry_decorator()


class ResilientChatGoogleGenerativeAI(ChatGoogleGenerativeAI):
    """ChatGoogleGenerativeAI subclass wrapped with tenacity exponential retry on invocation."""

    @llm_retry
    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return super().invoke(*args, **kwargs)

    @llm_retry
    def generate(self, *args: Any, **kwargs: Any) -> Any:
        return super().generate(*args, **kwargs)

    @llm_retry
    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return await super().ainvoke(*args, **kwargs)


class ResilientGoogleGenerativeAIEmbeddings(GoogleGenerativeAIEmbeddings):
    """GoogleGenerativeAIEmbeddings subclass wrapped with tenacity retry on query and documents."""

    @llm_retry
    def embed_query(self, text: str) -> List[float]:
        return super().embed_query(text)

    @llm_retry
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return super().embed_documents(texts)


class LocalHuggingFaceEmbeddings(Embeddings):
    """Local embedding model powered by SentenceTransformer."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        logger.info("Initializing local SentenceTransformer model: %s", model_name)
        self._model_name = model_name
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        embedding = self._model.encode([text], convert_to_numpy=True)
        return embedding[0].tolist()


def get_llm(
    model: Optional[str] = None,
    temperature: float = 0.1,
    settings: Optional[Settings] = None,
) -> ChatGoogleGenerativeAI:
    """Retrieve an initialized ChatGoogleGenerativeAI instance with retry capabilities.

    Args:
        model: Optional model name override.
        temperature: Sampling temperature (default 0.1).
        settings: Optional Settings instance override.

    Returns:
        Configured ChatGoogleGenerativeAI model.

    Raises:
        ValueError: If GOOGLE_API_KEY is missing.
    """
    cfg = settings or get_settings()
    api_key = cfg.require_google_api_key()
    selected_model = model or cfg.llm_model

    logger.debug("Instantiating ChatGoogleGenerativeAI with model=%s", selected_model)
    return ResilientChatGoogleGenerativeAI(
        model=selected_model,
        google_api_key=api_key,
        temperature=temperature,
    )


def get_embeddings(settings: Optional[Settings] = None) -> Embeddings:
    """Retrieve an initialized Embeddings instance according to application settings.

    Args:
        settings: Optional Settings instance override.

    Returns:
        An Embeddings implementation (Gemini or Local HuggingFace).

    Raises:
        ValueError: If Gemini provider is chosen but GOOGLE_API_KEY is missing.
    """
    cfg = settings or get_settings()
    provider = cfg.embedding_provider.lower().strip()

    if provider == "gemini":
        api_key = cfg.require_google_api_key()
        logger.debug(
            "Instantiating Gemini embeddings with model=%s",
            cfg.gemini_embedding_model,
        )
        return ResilientGoogleGenerativeAIEmbeddings(
            model=cfg.gemini_embedding_model,
            google_api_key=api_key,
        )
    elif provider == "local":
        logger.debug(
            "Instantiating local embeddings with model=%s",
            cfg.local_embedding_model,
        )
        return LocalHuggingFaceEmbeddings(model_name=cfg.local_embedding_model)
    else:
        raise ValueError(
            f"Unsupported embedding provider: '{provider}'. "
            f"Supported providers are 'gemini' and 'local'."
        )
