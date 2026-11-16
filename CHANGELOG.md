# Changelog

All notable changes to this project will be documented in this file.

## [Phase 1] - Initial Scaffold and Gemini Connectivity
### Added
- Project scaffold and directory structure (`app/`, `ui/`, `scripts/`, `tests/`, `data/`, `demo_repo/`).
- `requirements.txt` with pinned-compatible dependencies for LangChain, LangGraph, Chroma, Google GenAI, Sentence-Transformers, FastAPI, and Streamlit.
- `.gitignore` and `.env.example` configurations.
- `app/logging_setup.py`: Standard logging configuration with structured formatting and log routing.
- `app/config.py`: Pydantic-settings based typed configuration loading `.env` with validation and helpful missing API key diagnostics.
- `app/models.py`: Initial placeholder module for domain and schema models.
- `app/llm.py`: Resilient factories for `ChatGoogleGenerativeAI` and embeddings (`gemini` and `local` HuggingFace) with exponential backoff retries via Tenacity for rate limits.
- `scripts/check_setup.py`: Verification utility testing Python version, environment configuration, LLM generation, vector embeddings, and Chroma collection management.
- `tests/test_config.py`: Pytest suite verifying settings parsing and error handling for missing credentials.
