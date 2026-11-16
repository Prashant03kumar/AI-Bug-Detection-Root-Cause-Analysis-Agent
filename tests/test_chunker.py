"""Unit tests for AST chunking pipeline."""

from pathlib import Path
import pytest
from app.indexing.chunker import chunk_file, chunk_repository, is_test_file


@pytest.fixture
def temp_fixture_repo(tmp_path: Path) -> Path:
    """Create a temporary Python project structure for AST testing."""
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir(parents=True)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)

    # 1. Standard module with function and class
    calc_code = '''"""Math utility functions."""
import math
from typing import List


def compute_sum(a: int, b: int) -> int:
    """Calculate sum of two numbers."""
    return a + b


class MathEngine:
    """Mathematical calculations engine."""

    def multiply(self, a: int, b: int) -> int:
        """Multiply two values."""
        return a * b
'''
    (pkg_dir / "calc.py").write_text(calc_code, encoding="utf-8")

    # 2. Syntax error file
    broken_code = '''def broken_func(
    x = 10
    syntax error here!
'''
    (pkg_dir / "broken.py").write_text(broken_code, encoding="utf-8")

    # 3. Test file
    test_code = '''"""Test suite."""
def test_dummy():
    assert 1 == 1
'''
    (tests_dir / "test_calc.py").write_text(test_code, encoding="utf-8")

    return tmp_path


def test_is_test_file():
    """Verify test file path detection."""
    assert is_test_file("tests/test_sample.py") is True
    assert is_test_file("src/test_calc.py") is True
    assert is_test_file("shopapp/users.py") is False


def test_chunk_function_and_class(temp_fixture_repo: Path):
    """Verify function, class, and method AST chunks are properly created."""
    calc_file = temp_fixture_repo / "pkg" / "calc.py"
    chunks = chunk_file(calc_file, repo_root=temp_fixture_repo)

    symbols = {c.symbol_name: c for c in chunks}
    kinds = {c.kind for c in chunks}

    assert "module" in kinds
    assert "function" in kinds
    assert "class" in kinds
    assert "method" in kinds

    # Verify function chunk
    assert "compute_sum" in symbols
    func_chunk = symbols["compute_sum"]
    assert func_chunk.kind == "function"
    assert func_chunk.start_line == 6
    assert func_chunk.is_test is False
    assert "# file: pkg/calc.py | symbol: compute_sum" in func_chunk.text

    # Verify class & method chunks
    assert "MathEngine" in symbols
    class_chunk = symbols["MathEngine"]
    assert class_chunk.kind == "class"
    assert "multiply" in class_chunk.text

    assert "MathEngine.multiply" in symbols
    method_chunk = symbols["MathEngine.multiply"]
    assert method_chunk.kind == "method"


def test_syntax_error_fallback(temp_fixture_repo: Path):
    """Verify syntax error falls back to sliding line windows without crashing."""
    broken_file = temp_fixture_repo / "pkg" / "broken.py"
    chunks = chunk_file(broken_file, repo_root=temp_fixture_repo)

    assert len(chunks) > 0
    for c in chunks:
        assert c.kind == "window"
        assert "window_" in c.symbol_name


def test_test_file_flag(temp_fixture_repo: Path):
    """Verify test files receive is_test=True attribute."""
    test_file = temp_fixture_repo / "tests" / "test_calc.py"
    chunks = chunk_file(test_file, repo_root=temp_fixture_repo)

    assert len(chunks) > 0
    for c in chunks:
        assert c.is_test is True


def test_chunk_repository_walk(temp_fixture_repo: Path):
    """Verify walking entire repository aggregates all file chunks."""
    all_chunks = chunk_repository(temp_fixture_repo)
    assert len(all_chunks) >= 5
