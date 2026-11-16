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

## [Phase 2] - Target Demo Codebase, Real Git History & Injected Bugs
### Added
- Modular e-commerce target codebase `demo_repo/shopapp/` (pure Python, 700+ lines, typed and documented) with cross-module checkout orchestration (`orders -> payments -> inventory -> notifications`).
- Clean baseline test suite (`demo_repo/tests/test_clean.py`) with 6 passing unit tests on `clean-v1.0`.
- Scenario runner (`demo_repo/run_scenarios.py`) reproducing 10 distinct failure scenarios on HEAD.
- Idempotent git history generation script (`scripts/build_demo_repo.py`) creating 12 clean developer commits across multiple authors, tagging `clean-v1.0`, and injecting 10 separate bug commits:
  - `BUG-01`: None/undefined access (`shopapp/users.py::get_user_notification_preference`)
  - `BUG-02`: Off-by-one tier iteration (`shopapp/discounts.py::calculate_bulk_discount`)
  - `BUG-03`: Wrong comparison operator `>` vs `>=` in stock check (`shopapp/inventory.py::check_and_reserve_stock`)
  - `BUG-04`: Missing null-check after coupon refactor (`shopapp/cart.py::apply_coupon_to_cart`)
  - `BUG-05`: Float rounding precision drift in monetary breakdown (`shopapp/payments.py::calculate_payment_breakdown`)
  - `BUG-06`: Wrong dictionary key `item_id` vs `product_id` (`shopapp/orders.py::assemble_order_items`)
  - `BUG-07`: Mutable default argument leaking channels across requests (`shopapp/notifications.py::queue_notification`)
  - `BUG-08`: Swallowed exception masking invalid database saves (`shopapp/db.py::save`)
  - `BUG-09`: Stale warehouse inventory cache from omitted invalidation (`shopapp/inventory.py::check_and_reserve_stock`)
  - `BUG-10`: Wrong unit conversion dividing amount by 100 (`shopapp/payments.py::format_gateway_payload`)
- Test and evaluation data:
  - `data/bugs/BUG-01/` through `data/bugs/BUG-10/` with live-generated `error.txt` and `app.log`.
  - `data/logs/app.log` combining scenario execution logs.
  - `data/tickets/tickets.json` containing 15 historical tickets (8 similar to injected bugs, 7 distractors).
  - `eval/ground_truth.json` linking all 10 bugs to introducing commit hashes, root causes, file locations, line ranges, and fix instructions.
- Verification script `scripts/verify_ground_truth.py` verifying file existence, AST functions, line numbers, and git commit history for all 10 bugs.

## [Phase 3] - Code Indexing Pipeline (AST Chunking -> Embeddings -> Chroma)
### Added
- AST Code Chunker (`app/indexing/chunker.py`):
  - Traverses target repository, filters ignored directories, detects test code.
  - Extracts module overview chunks, top-level function chunks, class signature/docstring chunks, and class method chunks with call hierarchy and import usage tracking.
  - Prepends location and symbol metadata headers (`# file: ... | symbol: ...`).
  - Fallback sliding line-window chunking for syntax-error files.
- Persistent Vector Indexer (`app/indexing/indexer.py`):
  - `build_code_index`: Chunks codebase, batches embeddings (respecting Gemini API rate limits), and stores chunks with rich metadata in Chroma `code_chunks` collection.
  - `build_ticket_index`: Formats and indexes historical bug tickets into Chroma `bug_tickets` collection.
  - Full rebuild and incremental indexing modes using SHA-256 content hashes in `file_hashes.json`.
- Hybrid Code & Ticket Retriever (`app/indexing/retriever.py`):
  - `search_code_chunks`: Cosine similarity search with hybrid score boosting for exact symbol and file name matches.
  - `search_tickets`: Semantic similarity search across historical bug tickets.
- CLI & Testing Scripts:
  - `scripts/build_index.py`: CLI tool for full and incremental repository and ticket indexing.
  - `scripts/test_retrieval.py`: Benchmark script evaluating top-5 retrieval accuracy against ground truth for all 10 bug scenarios (achieved 10/10 hits, 100.0%).
  - `tests/test_chunker.py`: Unit tests for AST function, class, module overview, and syntax error windowing on isolated fixture repos.
  - `tests/test_retriever.py`: Unit tests for code chunk retrieval, hybrid boosting, and ticket queries using deterministic fake embeddings (no live API dependency).

## [Phase 4] - Investigation Tools
### Added
- Sandboxed Tool Infrastructure (`app/tools/common.py`):
  - Path traversal and boundary sandboxing resolving paths strictly within `TARGET_REPO_PATH`.
  - Output truncation helper capping tool responses to 3000 characters with `[truncated]` marker.
- 11 LangChain `@tool` implementations in `app/tools/`:
  - `parse_error`: Parses Python/JS/Java tracebacks and symptom logs into structured error types, messages, ordered stack frames, crash frames, and candidate keywords.
  - `search_code`: Queries the Chroma vector code index with formatted results and code snippets.
  - `read_file`: Sandboxed numbered source code reader with window centering.
  - `get_function_source`: Extracts complete AST source code for functions and class methods.
  - `find_callers`: Scans repository AST to identify functions/methods invoking a target symbol.
  - `find_callees`: Scans function bodies to identify all outbound calls.
  - `git_blame`: Sandboxed line-by-line revision history grouping lines by commit, author, timestamp, and message.
  - `recent_commits`: Repository or file-level git log inspector.
  - `show_commit_diff`: Unified patch and diff viewer for individual commits.
  - `search_logs`: Grep-like search across application logs with timestamp and severity level filters.
  - `find_similar_bugs`: Historical bug ticket similarity search against `bug_tickets` collection.
- Registry (`app/tools/__init__.py`):
  - `ALL_TOOLS` list and `TOOL_DESCRIPTIONS` dictionary for agent orchestration.
- Verification & Benchmarking:
  - `tests/test_tools.py`: Unit tests for all 11 tools, directory traversal sandboxing rejection, and `parse_error` verification across all 10 bug scenarios.
  - `scripts/demo_tools.py`: Chained investigation demo (`parse_error` -> `read_file` -> `git_blame` -> `show_commit_diff`) on BUG-01.
  - `scripts/check_blame_accuracy.py`: Validated that `git_blame` correctly identifies the true introducing commit for 10/10 bugs (100.0%, exceeding required 8/10).
  - `scripts/test_gemini_tools.py`: Verified live Gemini model tool-binding and tool-call generation targeting `git_blame`.

## [Phase 5] - Autonomous LangGraph Investigation Agent with Structured Grounding
### Added
- Domain Models (`app/models.py`):
  - `Evidence`: Structured record capturing evidence kind (`code`, `log`, `commit`, `ticket`, `diff`), file/commit source, raw snippet, and relevance justification.
  - `RootCauseReport`: Pydantic model enforcing structured diagnostic output including summary, root cause explanation, bug type category, exact file/function/line coordinates, introducing commit hash, gathered evidence chain, unified-diff suggested fix, confidence score (0.0 - 1.0) with reasoning, open questions, and post-hoc grounding flags.
- Agent State and Prompts:
  - `app/agent/state.py`: LangGraph state schema (`AgentState`, `Hypothesis`) tracking conversation message sequence, parsed error context, working hypotheses, verified evidence, step counts, and final structured reports.
  - `app/agent/prompts.py`: Senior debugging engineer system prompts enforcing systematic diagnostic procedure (parse -> inspect crash frame -> follow callers/callees upstream -> git blame/diff -> logs -> hypothesis -> verify against evidence before concluding), prohibiting fabrication of unverified paths/commits.
- LangGraph Workflow Graph (`app/agent/graph.py`):
  - State machine with nodes: `parse_input` -> `investigate` (LLM with 11 bound tools) -> `tools` (ToolNode loop) -> `hypothesize` -> `verify` (hypothesis validation against gathered evidence with back-routing to `investigate` on discrepancies) -> `report` (structured extraction via `llm.with_structured_output(RootCauseReport)`).
  - Safety safeguards: loop and duplicate tool-call detection to suppress repetitive queries, hard step limits (`MAX_AGENT_STEPS`), graceful degradation for tool/LLM failures, and real-time streaming generator `stream_investigation()`.
- Grounding Validation (`app/agent/validate.py`):
  - Post-hoc fact checker validating that report files exist in repository, line ranges are within real file bounds, function names exist in file AST, and introducing commits exist in real git history. Automatically caps confidence at 0.40 and records diagnostic notes if ungrounded claims are detected.
- CLI Runner & Offline Testing:
  - `scripts/run_agent.py`: CLI driver supporting `--bug <ID>` and `--text "..."` with streaming thought traces, tool calls, and formatted terminal reports.
  - `tests/test_agent_offline.py`: Deterministic offline pytest suite validating LangGraph state transitions and step-limit enforcement using a scripted mock chat model.
- Live Agent Evaluation:
  - Validated live agent across 3 real injected bug scenarios (`BUG-01`, `BUG-03`, `BUG-06`), achieving 100% ground-truth alignment on introducing commits, offending files, functions, line numbers, and passing post-hoc grounding validation (`grounded=True`, `confidence=1.0`).




