"""Verification script for BugSleuth environment and connectivity."""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def check_python_version() -> bool:
    """Verify Python version is >= 3.11."""
    major, minor, micro = sys.version_info[:3]
    version_str = f"{major}.{minor}.{micro}"
    print(f"\n[1/5] Checking Python version: {version_str} ... ", end="")
    if (major, minor) >= (3, 11):
        print(f"PASS (Python {version_str} >= 3.11)")
        return True
    else:
        print(f"FAIL (Python {version_str} is below required 3.11)")
        return False


def check_env_loaded() -> bool:
    """Verify .env file is loaded and GOOGLE_API_KEY is present."""
    print("[2/5] Checking environment & API key configuration ... ", end="")
    try:
        from app.config import get_settings

        # Clear lru_cache in case env changed
        get_settings.cache_clear()
        settings = get_settings()
        api_key = settings.require_google_api_key()
        masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
        print(f"PASS (Model: {settings.llm_model}, Embedding: {settings.embedding_provider}, Key: {masked})")
        return True
    except Exception as exc:
        print(f"FAIL ({exc})")
        return False


def check_llm_call() -> bool:
    """Verify one real LLM call to Gemini."""
    print("[3/5] Testing Gemini LLM connectivity ('Reply with the single word: OK') ... ", end="")
    try:
        from app.llm import get_llm

        llm = get_llm()
        response = llm.invoke("Reply with the single word: OK")
        content = response.content if hasattr(response, "content") else str(response)
        clean_content = str(content).strip()
        print(f"PASS (Response: {clean_content!r})")
        return True
    except Exception as exc:
        print(f"FAIL ({exc})")
        return False


def check_embedding_call() -> bool:
    """Verify one real embedding call and report vector dimension."""
    try:
        from app.config import get_settings
        settings = get_settings()
        provider = settings.embedding_provider
    except Exception:
        provider = "unknown"

    print(f"[4/5] Testing embeddings generation (provider: {provider}) ... ", end="")
    try:
        from app.llm import get_embeddings

        embeddings = get_embeddings()
        sample_text = "BugSleuth test embedding query for connectivity check."
        vector = embeddings.embed_query(sample_text)
        dim = len(vector)
        if dim > 0:
            print(f"PASS (Vector dimension: {dim})")
            return True
        else:
            print("FAIL (Received empty vector)")
            return False
    except Exception as exc:
        print(f"FAIL ({exc})")
        return False


def check_chroma_db() -> bool:
    """Verify Chroma can create and delete a temporary collection."""
    print("[5/5] Testing Chroma vector DB collection create/delete ... ", end="")
    temp_dir = PROJECT_ROOT / "data" / "temp_chroma_check"
    try:
        import chromadb

        temp_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(temp_dir))
        collection_name = "test_check_setup"
        collection = client.create_collection(name=collection_name)
        collection.add(
            ids=["doc1"],
            documents=["Sample document content for sanity testing"],
        )
        count = collection.count()
        client.delete_collection(name=collection_name)

        # Cleanup temp directory
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

        if count == 1:
            print("PASS (Collection created, populated, and deleted successfully)")
            return True
        else:
            print(f"FAIL (Unexpected document count: {count})")
            return False
    except Exception as exc:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"FAIL ({exc})")
        return False


def main() -> int:
    """Run all verification checks and return exit code."""
    print("=" * 60)
    print(" BugSleuth Phase 1 Environment & Connectivity Verification")
    print("=" * 60)

    results = [
        ("Python Version", check_python_version()),
        ("Environment / Config", check_env_loaded()),
        ("Gemini LLM Call", check_llm_call()),
        ("Embedding Generation", check_embedding_call()),
        ("Chroma Vector DB", check_chroma_db()),
    ]

    print("\n" + "=" * 60)
    print(" Summary:")
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  - {name:25s}: {status}")
        if not passed:
            all_passed = False
    print("=" * 60)

    if all_passed:
        print("All checks PASSED successfully!\n")
        return 0
    else:
        print("Some checks FAILED. Please review the errors above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
