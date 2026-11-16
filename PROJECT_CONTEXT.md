You are my senior engineer building "BugSleuth", an AI Bug Detection &
Root-Cause Analysis Agent, end to end. Save this message as PROJECT_CONTEXT.md
in the repo root and re-read it before every task.

WHAT IT DOES
Input: an error message / stack trace / log snippet / bug description.
The system investigates a target codebase like a senior engineer and returns:
root cause, file + line, evidence (code, git commits, logs, similar past bugs),
suggested fix, and a confidence score.

HOW IT WORKS
One-time: target repo -> AST chunking by function/class -> embeddings ->
Chroma vector DB (also index past bug tickets).
Per bug: parse input -> LangGraph agent loop that calls tools
(search_code, read_file, git_blame, recent_commits, search_logs,
find_similar_bugs) -> form hypothesis -> verify -> structured final report.

TECH STACK (fixed, do not substitute without asking)
- Python 3.11+, virtual env already created at .venv (do not recreate it)
- LLM: Google Gemini via langchain-google-genai (model name read from .env)
- Embeddings: Gemini embeddings by default, local sentence-transformers as
  fallback, switchable via .env
- Orchestration: LangGraph + LangChain
- Vector DB: Chroma (persistent, local)
- Parsing: Python ast module (target codebase is Python)
- Git: GitPython
- Backend: FastAPI; Frontend: Streamlit
- Validation: Pydantic v2; Tests: pytest; Config: python-dotenv

RULES
1. Work phase by phase. Only do what the current prompt asks.
2. After writing code, RUN it and RUN the tests. Never claim something works
   without showing real command output.
3. If something fails, debug it and fix it; do not skip it.
4. Never hardcode secrets. Read them from .env. Keep .env in .gitignore and
   maintain a .env.example.
5. Every module gets type hints, docstrings, and logging (not print).
6. All LLM and embedding calls must have retry with exponential backoff and
   clear error messages for rate limits (free-tier Gemini).
7. Keep a CHANGELOG.md; after each phase append what was built and verified.
8. At the end of each phase give me: files created, commands to run, and
   the verification results.

Acknowledge you've read this, save PROJECT_CONTEXT.md, and wait for Phase 1.