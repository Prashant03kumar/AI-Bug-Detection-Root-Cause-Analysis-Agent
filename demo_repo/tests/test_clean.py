"""Unit test suite for ShopApp clean baseline."""

import pytest
from shopapp.db import db
from shopapp.users import get_user, create_user, get_user_notification_preference
from shopapp.inventory import get_stock, check_and_reserve_stock, restock_product
from shopapp.discounts import calculate_bulk_discount, get_tier_discount_rate
from shopapp.cart import create_cart, add_item_to_cart, apply_coupon_to_cart, calculate_cart_subtotal
from shopapp.payments import calculate_payment_breakdown, process_payment, format_gateway_payload
from shopapp.notifications import queue_notification, send_order_confirmation
from shopapp.orders import place_order


@pytest.fixture(autouse=True)
def reset_database():
    db.reset()
    yield
    db.reset()


def test_user_creation_and_preferences():
    user = create_user("Test User", "test@test.com", "gold")
    assert user["name"] == "Test User"
    assert get_user_notification_preference(user["id"], "email") is True


def test_inventory_check_and_reserve():
    assert check_and_reserve_stock("prod_101", 5) is True
    assert get_stock("prod_101") == 0
    assert check_and_reserve_stock("prod_101", 1) is False
    restock_product("prod_101", 10)
    assert get_stock("prod_101") == 10


def test_bulk_discount_calculation():
    # 25 items at $10 each -> 20% discount = $50.00
    discount = calculate_bulk_discount(25, 10.0)
    assert discount == 50.0
    assert get_tier_discount_rate("gold") == 0.15


def test_cart_operations_and_coupon():
    cart = create_cart("usr_001")
    add_item_to_cart(cart["id"], "prod_102", 2)
    subtotal = calculate_cart_subtotal(db.get("carts", cart["id"]))
    assert subtotal == 99.0
    apply_coupon_to_cart(cart["id"], "SAVE20")
    updated_cart = db.get("carts", cart["id"])
    assert updated_cart["discount_percent"] == 20.0


def test_payments_breakdown_and_processing():
    breakdown = calculate_payment_breakdown(100.0)
    assert breakdown["tax"] == 8.25
    assert breakdown["fee"] == 2.00
    assert breakdown["total"] == 110.25
    payload = format_gateway_payload(110.25)
    assert payload["amount"] == 11025


def test_order_placement_clean():
    cart = create_cart("usr_001")
    add_item_to_cart(cart["id"], "prod_102", 1)
    order = place_order("usr_001", cart["id"])
    assert order["status"] == "confirmed"
    assert order["final_total"] > 0
