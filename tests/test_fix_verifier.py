"""Tests for auto-fix patch verification in isolated sandbox."""

from pathlib import Path
import pytest

from app.agent.fix_verifier import extract_diff_patch, verify_fix_in_temp_repo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_REPO = PROJECT_ROOT / "demo_repo"


def test_extract_diff_patch_from_fenced_markdown():
    """Verify extract_diff_patch parses code fence."""
    sample_text = (
        "Here is the recommended solution:\n"
        "```diff\n"
        "--- a/shopapp/users.py\n"
        "+++ b/shopapp/users.py\n"
        "@@ -10,2 +10,2 @@\n"
        "-old\n"
        "+new\n"
        "```\n"
        "This resolves the issue."
    )
    patch = extract_diff_patch(sample_text)
    assert patch is not None
    assert "--- a/shopapp/users.py" in patch
    assert "+new" in patch


def test_extract_diff_patch_raw():
    """Verify extract_diff_patch parses raw diff."""
    raw = (
        "--- a/shopapp/inventory.py\n"
        "+++ b/shopapp/inventory.py\n"
        "@@ -40,3 +40,3 @@\n"
        "-    if stock > quantity:\n"
        "+    if stock >= quantity:\n"
    )
    patch = extract_diff_patch(raw)
    assert patch is not None
    assert "stock >=" in patch


def test_verify_fix_bug_01():
    """Test auto-fix verification on BUG-01 in temporary demo_repo copy."""
    patch_01 = """--- a/shopapp/users.py
+++ b/shopapp/users.py
@@ -34,5 +34,7 @@
     user = get_user(user_id)
     if not user:
         return False
+    if user.get("preferences") is None:
+        return True
     # BUG-01: Direct subscript without null-check on user["preferences"]
     return bool(user["preferences"][channel])
"""
    result = verify_fix_in_temp_repo(DEMO_REPO, patch_01, bug_hint="BUG-01")
    assert result.patch_applied is True
    assert result.fix_verified is True
    assert "0/1 failures reproduced" in result.test_output or "[PASS]" in result.test_output


def test_verify_fix_bug_03():
    """Test auto-fix verification on BUG-03 in temporary demo_repo copy."""
    patch_03 = """--- a/shopapp/inventory.py
+++ b/shopapp/inventory.py
@@ -40,5 +40,5 @@
     stock = get_stock(product_id)
     # BUG-03: Wrong operator (> instead of >=) rejects purchases for exact remaining stock
-    if stock > quantity:
+    if stock >= quantity:
         new_stock = stock - quantity
         db.save("inventory", product_id, {"product_id": product_id, "stock": new_stock})
"""
    result = verify_fix_in_temp_repo(DEMO_REPO, patch_03, bug_hint="BUG-03")
    assert result.patch_applied is True
    assert result.fix_verified is True
    assert "0/1 failures reproduced" in result.test_output or "[PASS]" in result.test_output


def test_verify_fix_invalid_patch():
    """Verify fix verifier handles invalid patches gracefully without crashing."""
    bad_patch = """--- a/non_existent.py
+++ b/non_existent.py
@@ -1,1 +1,1 @@
-invalid
+invalid
"""
    result = verify_fix_in_temp_repo(DEMO_REPO, bad_patch)
    assert result.patch_applied is False
    assert result.fix_verified is False
    assert "git apply failed" in result.error_message.lower()
