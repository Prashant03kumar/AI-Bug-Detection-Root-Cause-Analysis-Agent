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

