# BugSleuth 🔍

BugSleuth is an AI-powered Bug Detection & Root-Cause Analysis Agent.

## Overview
Given an error message, stack trace, log snippet, or bug description, BugSleuth investigates the target codebase, forms hypotheses, inspects code and git history, searches logs, and produces a structured root-cause analysis report with suggested fixes.

## Architecture
- **Orchestration**: LangGraph + LangChain
- **LLM**: Google Gemini
- **Vector DB**: Chroma (persistent AST-indexed code and past tickets)
- **Code & VCS**: Python AST parser + GitPython
- **Interfaces**: FastAPI backend + Streamlit dashboard

## Setup
1. Create and activate a Python 3.11+ virtual environment (`.venv`).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy environment configuration:
   ```bash
   cp .env.example .env
   ```
   Add your `GOOGLE_API_KEY` to `.env`.
4. Run environment check:
   ```bash
   python scripts/check_setup.py
   ```
