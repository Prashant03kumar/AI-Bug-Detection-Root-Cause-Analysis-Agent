"""Order placement and cross-module checkout pipeline."""

from typing import Any, Dict, List
from shopapp.cart import calculate_cart_subtotal, get_cart
from shopapp.db import db
from shopapp.discounts import get_tier_discount_rate
from shopapp.inventory import check_and_reserve_stock
from shopapp.notifications import send_order_confirmation
from shopapp.payments import calculate_payment_breakdown, process_payment
from shopapp.users import get_user
from shopapp.utils import generate_id


def assemble_order_items(cart_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format cart items into standardized order line items."""
    order_items = []
    for item in cart_items:
        # BUG-06: Wrong dict key 'item_id' instead of 'product_id'
        order_items.append({
            "product_id": item["item_id"],
            "name": item["name"],
            "quantity": item["quantity"],
            "unit_price": item["price"],
        })
    return order_items


def place_order(
    user_id: str,
    cart_id: str,
    payment_method: str = "credit_card",
    shipping_address: str = "123 Main St",
) -> Dict[str, Any]:
    """Execute end-to-end checkout flow across modules."""
    user = get_user(user_id)
    if not user:
        raise ValueError(f"User '{user_id}' does not exist")
    cart = get_cart(cart_id)
    if not cart or not cart.get("items"):
        raise ValueError("Cannot place order with an empty cart")

    # 1. Assemble items
    line_items = assemble_order_items(cart["items"])

    # 2. Check and reserve inventory
    for item in line_items:
        reserved = check_and_reserve_stock(item["product_id"], item["quantity"])
        if not reserved:
            raise RuntimeError(f"Insufficient stock for product '{item['product_id']}'")

    # 3. Calculate discounts & total
    subtotal = calculate_cart_subtotal(cart)
    tier_discount_rate = get_tier_discount_rate(user.get("tier", "standard"))
    coupon_discount_rate = cart.get("discount_percent", 0.0) / 100.0
    discount_rate = max(tier_discount_rate, coupon_discount_rate)
    discounted_subtotal = round(subtotal * (1.0 - discount_rate), 2)

    breakdown = calculate_payment_breakdown(discounted_subtotal)
    final_total = breakdown["total"]

    # 4. Process payment
    order_id = generate_id("ord")
    payment = process_payment(order_id, user_id, final_total, payment_method)

    # 5. Save order
    order_record = {
        "id": order_id,
        "user_id": user_id,
        "items": line_items,
        "subtotal": subtotal,
        "final_total": final_total,
        "breakdown": breakdown,
        "payment_id": payment["transaction_id"],
        "shipping_address": shipping_address,
        "status": "confirmed",
    }
    db.save("orders", order_id, order_record)

    # 6. Send notification
    send_order_confirmation(user_id, order_id, final_total)

    # 7. Clear cart
    cart["items"] = []
    cart["coupon_code"] = None
    cart["discount_percent"] = 0.0
    db.save("carts", cart_id, cart)

    return order_record
