"""Inventory management and stock reservation."""

from typing import Dict, Optional
from shopapp.db import db

_STOCK_CACHE: Dict[str, int] = {}


def get_stock(product_id: str) -> int:
    """Retrieve current available stock for a product."""
    record = db.get("inventory", product_id)
    if not record:
        return 0
    return record.get("stock", 0)


def get_stock_with_cache(product_id: str) -> int:
    """Retrieve cached stock quantity for high-throughput reads."""
    global _STOCK_CACHE
    if product_id in _STOCK_CACHE:
        return _STOCK_CACHE[product_id]
    stock = get_stock(product_id)
    _STOCK_CACHE[product_id] = stock
    return stock


def invalidate_stock_cache(product_id: Optional[str] = None) -> None:
    """Clear warehouse stock cache."""
    global _STOCK_CACHE
    if product_id:
        _STOCK_CACHE.pop(product_id, None)
    else:
        _STOCK_CACHE.clear()


def check_and_reserve_stock(product_id: str, quantity: int) -> bool:
    """Verify stock availability and reserve the requested quantity."""
    if quantity <= 0:
        return False
    stock = get_stock(product_id)
    # BUG-03: Wrong operator (> instead of >=) rejects purchases for exact remaining stock
    if stock > quantity:
        new_stock = stock - quantity
        db.save("inventory", product_id, {"product_id": product_id, "stock": new_stock})
        # BUG-09: Stock cache invalidation call commented out, causing stale cache reads
        # invalidate_stock_cache(product_id)
        return True
    return False


def restock_product(product_id: str, quantity: int) -> int:
    """Add new inventory units for a product."""
    current = get_stock(product_id)
    new_stock = current + quantity
    db.save("inventory", product_id, {"product_id": product_id, "stock": new_stock})
    invalidate_stock_cache(product_id)
    return new_stock
