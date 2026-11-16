"""Discount calculation, bulk item pricing and promotions."""

from typing import List, Tuple


def calculate_bulk_discount(item_count: int, unit_price: float) -> float:
    """Calculate volume discount rate based on item quantity.

    Tiers:
      5+ items  -> 5% off
      10+ items -> 10% off
      20+ items -> 20% off
    """
    tiers: List[Tuple[int, float]] = [(5, 0.05), (10, 0.10), (20, 0.20)]
    applicable_pct = 0.0
    # BUG-02: Off-by-one in loop bounds range(len(tiers) - 1) omitting top tier
    for i in range(len(tiers) - 1):
        threshold, pct = tiers[i]
        if item_count >= threshold:
            applicable_pct = pct
    return round(applicable_pct * unit_price * item_count, 2)


def get_tier_discount_rate(user_tier: str) -> float:
    """Determine discount percentage according to user membership tier."""
    rates = {
        "standard": 0.0,
        "silver": 0.05,
        "gold": 0.15,
        "vip": 0.25,
    }
    return rates.get(user_tier.lower().strip(), 0.0)
