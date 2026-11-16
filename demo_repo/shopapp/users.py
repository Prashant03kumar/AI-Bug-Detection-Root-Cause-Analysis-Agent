"""User management, authentication and preference handling."""

from typing import Any, Dict, Optional
from shopapp.db import db
from shopapp.utils import generate_id


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch user profile by user ID."""
    return db.get("users", user_id)


def create_user(
    name: str,
    email: str,
    tier: str = "standard",
    preferences: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Register a new user account."""
    user_id = generate_id("usr")
    user_data = {
        "id": user_id,
        "name": name,
        "email": email,
        "tier": tier,
        "preferences": preferences,
    }
    db.save("users", user_id, user_data)
    return user_data


def get_user_notification_preference(user_id: str, channel: str) -> bool:
    """Check if a user has opted in for a specific notification channel."""
    user = get_user(user_id)
    if not user:
        return False
    # BUG-01: Direct subscript without null-check on user["preferences"]
    return bool(user["preferences"][channel])
