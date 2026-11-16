"""General utilities and helper functions for ShopApp."""

import hashlib
import time
from typing import Any, Dict


def generate_id(prefix: str) -> str:
    """Generate a unique prefixed identifier."""
    raw = f"{prefix}_{time.time_ns()}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{digest}"


def format_currency(amount: float) -> str:
    """Format floating point currency value into standard string format."""
    return f"${amount:,.2f}"


def sanitize_input(text: str) -> str:
    """Strip whitespace and dangerous characters from user input."""
    return text.strip() if text else ""
