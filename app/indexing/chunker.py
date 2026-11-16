"""AST-based code chunking engine for Python repositories."""

import ast
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Set

from app.logging_setup import get_logger
from app.models import CodeChunk

logger = get_logger("indexing.chunker")

IGNORED_DIRS: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "site-packages",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "build",
    "dist",
    ".idea",
    ".vscode",
}

MAX_FILE_SIZE_BYTES = 250_000  # 250 KB safety cap for large repos
MAX_FILE_LINES = 10_000


def is_test_file(rel_path: str) -> bool:
    """Determine whether a file path corresponds to test code."""
    parts = Path(rel_path).parts
    return (
        any(p == "tests" or p.startswith("test_") or p.endswith("_test") for p in parts)
        or Path(rel_path).name.startswith("test_")
        or Path(rel_path).name.endswith("_test.py")
    )


def extract_calls(node: ast.AST) -> List[str]:
    """Extract list of called function/method names within an AST subtree."""
    calls: Set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Name):
                calls.add(sub.func.id)
            elif isinstance(sub.func, ast.Attribute):
                if isinstance(sub.func.value, ast.Name):
                    calls.add(f"{sub.func.value.id}.{sub.func.attr}")
                else:
                    calls.add(sub.func.attr)
    return sorted(list(calls))


def extract_module_imports(tree: ast.AST) -> Dict[str, str]:
    """Map imported symbol aliases to their fully-qualified import names."""
    imports: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                imports[name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                name = alias.asname or alias.name
                imports[name] = f"{mod}.{alias.name}" if mod else alias.name
    return imports


def extract_used_imports(node: ast.AST, available_imports: Dict[str, str]) -> List[str]:
    """Identify which available module imports are actually referenced in an AST node."""
    used: Set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in available_imports:
            used.add(available_imports[sub.id])
    return sorted(list(used))


def make_chunk_id(file_path: str, symbol_name: str, start_line: int) -> str:
    """Generate a deterministic identifier for a code chunk."""
    raw = f"{file_path}:{symbol_name}:{start_line}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    # Clean symbol for ID prefix
    clean_sym = symbol_name.replace(" ", "_").replace("(", "").replace(")", "")
    return f"{Path(file_path).stem}_{clean_sym}_{digest}"


def fallback_line_window_chunking(
    file_path_str: str,
    source_lines: List[str],
    is_test: bool,
    window_size: int = 40,
    overlap: int = 10,
) -> List[CodeChunk]:
    """Fallback chunker using fixed-size sliding line windows when AST parsing fails."""
    chunks: List[CodeChunk] = []
    total_lines = len(source_lines)
    if total_lines == 0:
        return chunks

    step = max(1, window_size - overlap)
    for start_idx in range(0, total_lines, step):
        end_idx = min(total_lines, start_idx + window_size)
        start_line = start_idx + 1
        end_line = end_idx
        window_text = "".join(source_lines[start_idx:end_idx])
        symbol_name = f"window_{start_line}_{end_line}"
        header = f"# file: {file_path_str} | symbol: {symbol_name}\n"
        full_text = header + window_text.strip()

        chunks.append(
            CodeChunk(
                id=make_chunk_id(file_path_str, symbol_name, start_line),
                text=full_text,
                file_path=file_path_str,
                symbol_name=symbol_name,
                kind="window",
                start_line=start_line,
                end_line=end_line,
                is_test=is_test,
                imports_used=[],
                calls_made=[],
            )
        )
        if end_idx >= total_lines:
            break

    return chunks


def chunk_file(file_path: Path, repo_root: Path) -> List[CodeChunk]:
    """Parse a single Python file and produce structured AST code chunks.

    Args:
        file_path: Absolute or relative path to the Python file.
        repo_root: Path to the repository root directory.

    Returns:
        List of CodeChunk models extracted from the file.
    """
    rel_path_str = file_path.resolve().relative_to(repo_root.resolve()).as_posix()
    is_test = is_test_file(rel_path_str)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_content = f.read()
    except Exception as exc:
        logger.error("Failed to read file %s: %s", rel_path_str, exc)
        return []

    source_lines = source_content.splitlines(keepends=True)
    total_lines = len(source_lines)
    file_size = file_path.stat().st_size

    if file_size > MAX_FILE_SIZE_BYTES or total_lines > MAX_FILE_LINES:
        logger.warning(
            "Skipping detailed AST chunking for oversized file %s (%d bytes, %d lines)",
            rel_path_str,
            file_size,
            total_lines,
        )
        return [
            CodeChunk(
                id=make_chunk_id(rel_path_str, "oversized_file", 1),
                text=f"# file: {rel_path_str} | symbol: oversized_file\n[Oversized source file {file_size} bytes, {total_lines} lines - detailed AST skipped]",
                file_path=rel_path_str,
                symbol_name="oversized_file",
                kind="module",
                start_line=1,
                end_line=min(total_lines, 50),
                is_test=is_test,
                imports_used=[],
                calls_made=[],
            )
        ]

    try:
        tree = ast.parse(source_content, filename=str(file_path))
    except SyntaxError as syn_err:
        logger.warning(
            "SyntaxError parsing %s at line %s: %s. Falling back to sliding window chunking.",
            rel_path_str,
            syn_err.lineno,
            syn_err.msg,
        )
        return fallback_line_window_chunking(rel_path_str, source_lines, is_test)

    chunks: List[CodeChunk] = []
    module_imports = extract_module_imports(tree)

    # 1. Module Overview Chunk
    docstring = ast.get_docstring(tree) or ""
    top_level_symbols: List[str] = []
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            top_level_symbols.append(item.name)

    import_list_str = ", ".join(sorted(list(set(module_imports.values())))) or "none"
    symbols_str = ", ".join(top_level_symbols) or "none"
    module_symbol_name = Path(rel_path_str).stem
    module_text = (
        f"# file: {rel_path_str} | symbol: {module_symbol_name} (module overview)\n"
        f'"""{docstring}"""\n'
        f"Imports: {import_list_str}\n"
        f"Top-level symbols: {symbols_str}\n"
    ).strip()

    chunks.append(
        CodeChunk(
            id=make_chunk_id(rel_path_str, f"{module_symbol_name}_module", 1),
            text=module_text,
            file_path=rel_path_str,
            symbol_name=module_symbol_name,
            kind="module",
            start_line=1,
            end_line=total_lines if total_lines > 0 else 1,
            is_test=is_test,
            imports_used=sorted(list(set(module_imports.values()))),
            calls_made=[],
        )
    )

    # 2. Walk Top-Level Definitions
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", start_line)
            func_code = "".join(source_lines[start_line - 1 : end_line])
            func_calls = extract_calls(node)
            func_imports = extract_used_imports(node, module_imports)
            header = f"# file: {rel_path_str} | symbol: {node.name}\n"
            full_text = header + func_code.strip()

            chunks.append(
                CodeChunk(
                    id=make_chunk_id(rel_path_str, node.name, start_line),
                    text=full_text,
                    file_path=rel_path_str,
                    symbol_name=node.name,
                    kind="function",
                    start_line=start_line,
                    end_line=end_line,
                    is_test=is_test,
                    imports_used=func_imports,
                    calls_made=func_calls,
                )
            )

        elif isinstance(node, ast.ClassDef):
            class_start = node.lineno
            class_end = getattr(node, "end_lineno", class_start)
            class_doc = ast.get_docstring(node) or ""
            method_names: List[str] = []

            # Process Methods inside Class
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_names.append(item.name)
                    m_start = item.lineno
                    m_end = getattr(item, "end_lineno", m_start)
                    method_code = "".join(source_lines[m_start - 1 : m_end])
                    m_symbol = f"{node.name}.{item.name}"
                    m_calls = extract_calls(item)
                    m_imports = extract_used_imports(item, module_imports)
                    m_header = f"# file: {rel_path_str} | symbol: {m_symbol}\n"
                    m_full_text = m_header + method_code.strip()

                    chunks.append(
                        CodeChunk(
                            id=make_chunk_id(rel_path_str, m_symbol, m_start),
                            text=m_full_text,
                            file_path=rel_path_str,
                            symbol_name=m_symbol,
                            kind="method",
                            start_line=m_start,
                            end_line=m_end,
                            is_test=is_test,
                            imports_used=m_imports,
                            calls_made=m_calls,
                        )
                    )

            # Class Overview Chunk (class signature + docstring + method summary)
            methods_summary = ", ".join(method_names) if method_names else "none"
            class_header_text = (
                f"# file: {rel_path_str} | symbol: {node.name} (class)\n"
                f"class {node.name}:\n"
                f'    """{class_doc}"""\n'
                f"    # Methods: {methods_summary}\n"
            ).strip()

            chunks.append(
                CodeChunk(
                    id=make_chunk_id(rel_path_str, node.name, class_start),
                    text=class_header_text,
                    file_path=rel_path_str,
                    symbol_name=node.name,
                    kind="class",
                    start_line=class_start,
                    end_line=class_end,
                    is_test=is_test,
                    imports_used=[],
                    calls_made=[],
                )
            )

    return chunks


def chunk_repository(repo_path: Path | str) -> List[CodeChunk]:
    """Traverse a repository and chunk all valid Python source files.

    Args:
        repo_path: Directory path of the target codebase.

    Returns:
        Aggregated list of all extracted CodeChunk objects.
    """
    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Repository path does not exist: {root}")

    all_chunks: List[CodeChunk] = []
    py_files: List[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Exclude ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]
        for file in filenames:
            if file.endswith(".py"):
                py_files.append(Path(dirpath) / file)

    logger.info("Found %d Python source files in %s", len(py_files), root)
    for py_file in sorted(py_files):
        file_chunks = chunk_file(py_file, repo_root=root)
        all_chunks.extend(file_chunks)

    logger.info("Extracted %d total code chunks from repository", len(all_chunks))
    return all_chunks
