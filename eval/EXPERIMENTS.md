# BugSleuth Evaluation Experiments & Benchmark Analysis

This document records the experimental evaluation iterations, baseline benchmarks, and comparative findings for the BugSleuth Autonomous Root-Cause Analysis Agent.

---

## 1. Executive Summary

| System Configuration | File Localization | Function Match | Line Overlap | Commit Match | Bug Type Match | Semantic Quality (Judge) | Fact Grounding | Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline (Raw Gemini 3.5, No Tools / No RAG)** | 50.0% (5/10) | 50.0% (5/10) | 80.0% (8/10) | 0.0% (0/10) | 20.0% (2/10) | 83.0% | 0.0% | 13.93s |
| **BugSleuth Agent (LangGraph + RAG + Git Tools)** | **100.0% (10/10)** | **100.0% (10/10)** | **100.0% (10/10)** | **100.0% (10/10)** | **100.0% (10/10)** | **100.0%** | **100.0%** | 69.64s |
| **Net Performance Delta ($\Delta$)** | **+50.0%** | **+50.0%** | **+20.0%** | **+100.0%** | **+80.0%** | **+17.0%** | **+100.0%** | +55.71s |

---

## 2. Experiment 1: Raw Gemini Baseline (No Tools, No RAG)

### Setup & Methodology
- **Objective:** Establish the performance ceiling of a frontier LLM (`gemini-3.5-flash-lite`) operating solely on raw error text / stack traces without codebase indexing, file reading, AST analysis, git revision history, or runtime logs.
- **Input:** Raw `error.txt` from each bug scenario (`BUG-01` through `BUG-10`).
- **Prompt:** Instructed to deduce root cause, offending file, function, line range, introducing commit, bug type, and suggested fix purely from the error string.
- **Grounding:** Marked ungrounded by definition (`grounded: False`).

### Quantitative Results
- **File Localization:** 5/10 (50.0%)
- **Function Identification:** 5/10 (50.0%)
- **Introducing Commit Match:** 0/10 (0.0%)
- **Bug Type Classification:** 2/10 (20.0%)
- **LLM-Judge Semantic Quality:** 83.0%
- **Fact Grounding Rate:** 0.0%
- **Average Latency:** 13.93s per bug

### Failure Analysis & Qualitative Observations
1. **Traceback Blindness for Logic Bugs:** For bugs with explicit Python tracebacks (`BUG-01`, `BUG-04`, `BUG-05`, `BUG-06`), the baseline model was able to extract the file and function name verbatim from the stack trace frames. However, for bugs exhibiting runtime symptom logs or silent logic errors without tracebacks (`BUG-02`, `BUG-03`, `BUG-07`, `BUG-08`, `BUG-09`, `BUG-10`), the baseline was completely blind to where the offending code lived in the repository.
2. **Total Inability to Identify Introducing Commits:** Without access to Git repository tooling (`git_blame`, `show_commit_diff`), the baseline achieved 0.0% on commit identification. It was unable to determine when, why, or by whom regressions were introduced.
3. **Plausible Hallucination on Subtle Logic Bugs:** For `BUG-08` (swallowed exception in database save), the baseline guessed `shopapp/orders.py` instead of `shopapp/db.py`. For `BUG-09` (stale cache in stock check), it guessed an external cache module instead of `shopapp/inventory.py`.

---

## 3. Experiment 2: BugSleuth Autonomous Agent (LangGraph + RAG + Tools)

### Setup & Methodology
- **Objective:** Evaluate the full BugSleuth multi-agent investigation architecture across the identical 10 bug scenarios.
- **Components:**
  - Multi-stage LangGraph workflow (`parse_input` $\to$ `investigate` $\rightleftarrows$ `tools` $\to$ `hypothesize` $\to$ `verify` $\to$ `report`).
  - 11 sandboxed tools (`search_code`, `read_file`, `git_blame`, `show_commit_diff`, `find_callers`, `find_callees`, `search_logs`, `find_similar_bugs`).
  - AST-based persistent vector index (Chroma `code_chunks` and `bug_tickets`).
  - Post-hoc fact validation (`app/agent/validate.py`) checking file paths, line ranges, AST syntax trees, and git log history.
  - Strict LLM Judge using Gemini (`eval/metrics.py`) scoring root-cause semantic fidelity against `eval/ground_truth.json`.

### Quantitative Results
- **File Localization:** 10/10 (100.0%) — Target $\ge 70.0\%$ exceeded.
- **Function Identification:** 10/10 (100.0%)
- **Line Range Overlap:** 10/10 (100.0%)
- **Introducing Commit Match:** 10/10 (100.0%)
- **Bug Type Classification:** 10/10 (100.0%)
- **LLM-Judge Semantic Quality:** 100.0% (10/10 scored 1.00)
- **Fact Grounding Rate:** 100.0% (10/10 verified)
- **Confidence Calibration:** Calibrated (Average confidence 1.00 on verified correct answers)
- **Average Steps per Investigation:** 5.5 steps (well within the 12-step budget)
- **Average Latency:** 69.64s per bug

---

## 4. Granular Bug-by-Bug Comparison (Baseline vs. Agent)

| Bug ID | Error Signature | Baseline File | Agent File | Baseline Commit | Agent Commit | Baseline Semantic | Agent Semantic | Net Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BUG-01** | `TypeError: 'NoneType' object is not subscriptable` | `shopapp/users.py` | `shopapp/users.py` | None | `1f3a4df` (Asha) | 0.50 | 1.00 | **IMPROVED** |
| **BUG-02** | `CalculationMismatch: Bulk discount omitted 20% tier` | `shopapp/discounts.py` | `shopapp/discounts.py` | None | `ded162c` (Ravi) | 0.50 | 1.00 | **IMPROVED** |
| **BUG-03** | `InsufficientStockError: operator > rejected exact match` | *Missed* | `shopapp/inventory.py` | None | `b74219c` (Meera) | 1.00 | 1.00 | **IMPROVED** |
| **BUG-04** | `AttributeError: 'NoneType' object has no attribute 'get'` | `shopapp/cart.py` | `shopapp/cart.py` | None | `b116e78` (Asha) | 1.00 | 1.00 | **IMPROVED** |
| **BUG-05** | `PaymentValidationError: rounding precision drift` | `shopapp/payments.py` | `shopapp/payments.py` | None | `8a05e02` (Ravi) | 1.00 | 1.00 | **IMPROVED** |
| **BUG-06** | `KeyError: 'item_id'` | `shopapp/orders.py` | `shopapp/orders.py` | None | `047d159` (Meera) | 1.00 | 1.00 | **IMPROVED** |
| **BUG-07** | `NotificationLeakError: channels retained across calls` | *Missed* | `shopapp/notifications.py` | None | `0b1b95d` (Asha) | 0.80 | 1.00 | **IMPROVED** |
| **BUG-08** | `DatabaseAnomalyError: dropped record swallowed` | *Missed* | `shopapp/db.py` | None | `3505d38` (Ravi) | 0.50 | 1.00 | **IMPROVED** |
| **BUG-09** | `StaleInventoryError: cached stock out of sync` | *Missed* | `shopapp/inventory.py` | None | `d8d4d81` (Meera) | 1.00 | 1.00 | **IMPROVED** |
| **BUG-10** | `PaymentUnderchargeError: cents divided by 100` | *Missed* | `shopapp/payments.py` | None | `974749f` (Ravi) | 1.00 | 1.00 | **IMPROVED** |

---

## 5. Anti-Overfitting & Generalization Verification

To ensure that the 100% accuracy was achieved through genuine autonomous tool-based investigation and not through data leakage or hardcoding:

1. **Automated Leakage Test (`tests/test_no_ground_truth_leakage.py`):**
   - Automatically scans every Python file in `app/`.
   - Cross-references all 10 ground truth commit hashes (full and short hashes), bug identifiers (`BUG-01` .. `BUG-10`), root cause summaries, and fix descriptions.
   - Verified that zero ground-truth tokens or bug identifiers exist in the agent's codebase.
2. **Tool-Driven Grounding Verification (`app/agent/validate.py`):**
   - Inspects AST syntax trees of the demo repository to verify function existence.
   - Inspects physical file bounds on disk to verify line ranges.
   - Queries the real git commit history to ensure the reported introducing commit hash actually exists.
   - Enforces severe confidence penalties ($\le 0.40$) if ungrounded claims are made.
