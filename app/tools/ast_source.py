"""AST-based function source code extraction tool."""

import ast
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.logging_setup import get_logger
from app.tools.common import resolve_sandboxed_path, truncate_output

logger = get_logger("tools.ast_source")


class GetFunctionSourceArgs(BaseModel):
    """Input schema for get_function_source tool."""
    file: str = Field(..., description="File path relative to repository (e.g. 'shopapp/inventory.py')")
    symbol: str = Field(..., description="Function or method name (e.g. 'check_and_reserve_stock' or 'Database.save')")


def get_function_source_impl(file: str, symbol: str) -> str:
    """Extract complete source code of a specified function or method using AST."""
    try:
        abs_path, rel_path = resolve_sandboxed_path(file)
    except Exception as exc:
        return f"Error: {exc}"

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            source_content = f.read()
    except Exception as exc:
        return f"Error reading file '{rel_path}': {exc}"

    source_lines = source_content.splitlines(keepends=True)

    try:
        tree = ast.parse(source_content, filename=str(abs_path))
    except SyntaxError as syn_err:
        return f"Error: Syntax error in '{rel_path}' at line {syn_err.lineno}: {syn_err.msg}"

    target_symbol = symbol.strip()
    target_node = None
    target_kind = "function"

    if "." in target_symbol:
        class_name, method_name = target_symbol.split(".", 1)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                        target_node = item
                        target_kind = "method"
                        break
    else:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target_symbol:
                target_node = node
                target_kind = "function"
                break
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == target_symbol:
                        target_node = item
                        target_kind = f"method in class {node.name}"
                        break

    if target_node is None:
        return f"Error: Symbol '{symbol}' was not found in '{rel_path}'."

    start_line = target_node.lineno
    end_line = getattr(target_node, "end_lineno", start_line)

    lines_slice = source_lines[start_line - 1 : end_line]
    max_num_width = len(str(end_line))

    numbered_lines = []
    for offset, raw_line in enumerate(lines_slice):
        cur_line_num = start_line + offset
        num_str = str(cur_line_num).rjust(max_num_width)
        numbered_lines.append(f"{num_str} | {raw_line.rstrip(chr(10) + chr(13))}")

    header = f"# Symbol: {symbol} ({target_kind}) in {rel_path} (lines {start_line}-{end_line}):\n"
    return truncate_output(header + "\n".join(numbered_lines))


@tool("get_function_source", args_schema=GetFunctionSourceArgs)
def get_function_source(file: str, symbol: str) -> str:
    """Retrieve the full source code and line numbers of a specific function or class method via AST.

    Args:
        file: Relative path to file (e.g. 'shopapp/inventory.py').
        symbol: Function or method name (e.g. 'check_and_reserve_stock' or 'Database.save').

    Returns:
        Numbered lines of the function source code or an error message.
    """
    try:
        return get_function_source_impl(file, symbol)
    except Exception as exc:
        logger.error("get_function_source failed: %s", exc)
        return f"Error retrieving function source: {exc}"
