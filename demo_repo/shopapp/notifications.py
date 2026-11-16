"""Customer notifications and multi-channel dispatch."""

from typing import Any, Dict, List, Optional
from shopapp.db import db
from shopapp.utils import generate_id


# BUG-07: Mutable default argument channels=[] causes state leakage across calls
def queue_notification(
    user_id: str,
    message: str,
    channels: List[str] = [],
) -> List[str]:
    """Prepare and queue notification dispatch across channels."""
    channels.append(f"user_audit_{user_id}")
    target_channels = channels

    notif_id = generate_id("notif")
    db.save("notifications", notif_id, {
        "id": notif_id,
        "user_id": user_id,
        "message": message,
        "channels": target_channels,
    })
    return target_channels


def send_order_confirmation(
    user_id: str,
    order_id: str,
    total_amount: float,
) -> Dict[str, Any]:
    """Format and send order confirmation notification."""
    from shopapp.users import get_user_notification_preference

    channels = []
    if get_user_notification_preference(user_id, "email"):
        channels.append("email")
    if get_user_notification_preference(user_id, "sms"):
        channels.append("sms")

    message = f"Your order {order_id} for ${total_amount:.2f} has been confirmed."
    dispatched = queue_notification(user_id, message, channels)
    return {"order_id": order_id, "dispatched_channels": dispatched}
