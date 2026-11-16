"""Shopping cart management and total calculations."""

from typing import Any, Dict, List, Optional
from shopapp.db import db
from shopapp.utils import generate_id


def create_cart(user_id: str) -> Dict[str, Any]:
    """Create an empty shopping cart for a user."""
    cart_id = generate_id("cart")
    cart_data = {
        "id": cart_id,
        "user_id": user_id,
        "items": [],
        "coupon_code": None,
        "discount_percent": 0.0,
    }
    db.save("carts", cart_id, cart_data)
    return cart_data


def get_cart(cart_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve shopping cart by ID."""
    return db.get("carts", cart_id)


def add_item_to_cart(cart_id: str, product_id: str, quantity: int) -> Dict[str, Any]:
    """Add a product item to the shopping cart."""
    cart = get_cart(cart_id)
    if not cart:
        raise ValueError(f"Cart '{cart_id}' not found")
    product = db.get("products", product_id)
    if not product:
        raise ValueError(f"Product '{product_id}' not found")

    existing_item = next((it for it in cart["items"] if it["product_id"] == product_id), None)
    if existing_item:
        existing_item["quantity"] += quantity
    else:
        cart["items"].append({
            "product_id": product_id,
            "name": product["name"],
            "price": product["price"],
            "quantity": quantity,
        })
    db.save("carts", cart_id, cart)
    return cart


def apply_coupon_to_cart(cart_id: str, coupon_code: str) -> Dict[str, Any]:
    """Validate and apply a coupon code to the cart."""
    cart = get_cart(cart_id)
    if not cart:
        raise ValueError(f"Cart '{cart_id}' not found")
    coupon = db.get("coupons", coupon_code)
    # BUG-04: Missing null-check if coupon is None raises AttributeError
    if not coupon.get("is_active"):
        raise ValueError(f"Coupon '{coupon_code}' is expired or inactive")

    cart["coupon_code"] = coupon["code"]
    cart["discount_percent"] = float(coupon["discount_percent"])
    db.save("carts", cart_id, cart)
    return cart


def calculate_cart_subtotal(cart: Dict[str, Any]) -> float:
    """Calculate raw subtotal of items in cart."""
    subtotal = sum(item["price"] * item["quantity"] for item in cart.get("items", []))
    return round(subtotal, 2)
