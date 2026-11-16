"""Build the demo target repository (demo_repo) with authentic git history and injected bugs.

This script is fully idempotent: it rebuilds demo_repo/.git and all shopapp modules,
commits the clean baseline across multiple developer commits, tags clean-v1.0,
and then introduces 10 distinct bug commits covering all required bug types.
It also runs the scenarios to capture real stack traces/logs and generates:
- data/bugs/<bug_id>/error.txt and app.log
- data/logs/app.log
- data/tickets/tickets.json
- eval/ground_truth.json
"""

import ast
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_REPO = PROJECT_ROOT / "demo_repo"
DATA_DIR = PROJECT_ROOT / "data"
EVAL_DIR = PROJECT_ROOT / "eval"


def remove_readonly(func, path, exc_info):
    """Clear readonly bit and retry file removal on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def run_git(args: List[str], cwd: Path, env: Dict[str, str] | None = None) -> str:
    """Execute git command and return stripped stdout."""
    git_env = os.environ.copy()
    if env:
        git_env.update(env)
    res = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        env=git_env,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


# ============================================================================
# ShopApp Code Templates (Clean State)
# ============================================================================

SHOPAPP_INIT = '''"""ShopApp: Modular e-commerce backend demonstration."""

__version__ = "1.0.0"
'''

SHOPAPP_DB_CLEAN = '''"""In-memory database engine for ShopApp."""

from typing import Any, Dict, List, Optional


class Database:
    """Thread-safe in-memory key-value document database."""

    def __init__(self) -> None:
        self._tables: Dict[str, Dict[str, Dict[str, Any]]] = {
            "users": {},
            "products": {},
            "inventory": {},
            "carts": {},
            "orders": {},
            "payments": {},
            "coupons": {},
            "notifications": {},
        }
        self.seed_defaults()

    def seed_defaults(self) -> None:
        """Populate initial baseline records."""
        # Products & Inventory
        self._tables["products"]["prod_101"] = {
            "id": "prod_101",
            "name": "Wireless Mechanical Keyboard",
            "price": 89.99,
            "category": "electronics",
        }
        self._tables["inventory"]["prod_101"] = {"product_id": "prod_101", "stock": 5}

        self._tables["products"]["prod_102"] = {
            "id": "prod_102",
            "name": "Ergonomic Optical Mouse",
            "price": 49.50,
            "category": "electronics",
        }
        self._tables["inventory"]["prod_102"] = {"product_id": "prod_102", "stock": 50}

        self._tables["products"]["prod_103"] = {
            "id": "prod_103",
            "name": "USB-C Braided Cable 2m",
            "price": 12.00,
            "category": "accessories",
        }
        self._tables["inventory"]["prod_103"] = {"product_id": "prod_103", "stock": 100}

        # Users
        self._tables["users"]["usr_001"] = {
            "id": "usr_001",
            "name": "Alice Smith",
            "email": "alice@example.com",
            "tier": "gold",
            "preferences": {"email": True, "sms": False, "push": True},
        }
        self._tables["users"]["usr_002"] = {
            "id": "usr_002",
            "name": "Bob Guest",
            "email": "bob.guest@example.com",
            "tier": "standard",
            "preferences": None,  # Guest with uninitialized preferences
        }

        # Coupons
        self._tables["coupons"]["SAVE20"] = {
            "code": "SAVE20",
            "discount_percent": 20,
            "is_active": True,
        }
        self._tables["coupons"]["EXPIRED50"] = {
            "code": "EXPIRED50",
            "discount_percent": 50,
            "is_active": False,
        }

    def get(self, table: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by table and record ID."""
        if table not in self._tables:
            raise KeyError(f"Table '{table}' does not exist")
        record = self._tables[table].get(record_id)
        return record.copy() if record else None

    def save(self, table: str, record_id: str, data: Dict[str, Any]) -> bool:
        """Insert or update a document in a table."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid record data for '{table}': expected dict")
        if table not in self._tables:
            raise KeyError(f"Table '{table}' does not exist in database")
        self._tables[table][record_id] = data.copy()
        return True

    def delete(self, table: str, record_id: str) -> bool:
        """Delete a document by table and record ID."""
        if table in self._tables and record_id in self._tables[table]:
            del self._tables[table][record_id]
            return True
        return False

    def list_all(self, table: str) -> List[Dict[str, Any]]:
        """List all documents within a table."""
        if table not in self._tables:
            return []
        return [doc.copy() for doc in self._tables[table].values()]

    def reset(self) -> None:
        """Reset and reseed database."""
        for tbl in self._tables:
            self._tables[tbl].clear()
        self.seed_defaults()


# Global database instance
db = Database()
'''

SHOPAPP_UTILS_CLEAN = '''"""General utilities and helper functions for ShopApp."""

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
'''

SHOPAPP_USERS_CLEAN = '''"""User management, authentication and preference handling."""

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
    preferences = user.get("preferences")
    if preferences is None:
        return True  # Opt-in by default
    return preferences.get(channel, True)
'''

SHOPAPP_INVENTORY_CLEAN = '''"""Inventory management and stock reservation."""

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
    if stock >= quantity:
        new_stock = stock - quantity
        db.save("inventory", product_id, {"product_id": product_id, "stock": new_stock})
        invalidate_stock_cache(product_id)
        return True
    return False


def restock_product(product_id: str, quantity: int) -> int:
    """Add new inventory units for a product."""
    current = get_stock(product_id)
    new_stock = current + quantity
    db.save("inventory", product_id, {"product_id": product_id, "stock": new_stock})
    invalidate_stock_cache(product_id)
    return new_stock
'''

SHOPAPP_DISCOUNTS_CLEAN = '''"""Discount calculation, bulk item pricing and promotions."""

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
    for threshold, pct in tiers:
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
'''

SHOPAPP_CART_CLEAN = '''"""Shopping cart management and total calculations."""

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
    if coupon is None:
        raise ValueError(f"Coupon '{coupon_code}' does not exist")
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
'''

SHOPAPP_PAYMENTS_CLEAN = '''"""Payment processing, tax calculation, and gateway integration."""

from typing import Any, Dict
from shopapp.db import db
from shopapp.utils import generate_id


def format_gateway_payload(amount_in_dollars: float, currency: str = "USD") -> Dict[str, Any]:
    """Convert dollar amount to gateway specification (cents)."""
    amount_cents = int(round(amount_in_dollars * 100))
    return {
        "amount": amount_cents,
        "currency": currency.lower(),
        "charge_type": "standard",
    }


def calculate_payment_breakdown(
    subtotal: float,
    tax_rate: float = 0.0825,
    fee_rate: float = 0.02,
) -> Dict[str, float]:
    """Calculate tax, processing fee, and total payable amount with 2-decimal rounding."""
    tax = round(subtotal * tax_rate, 2)
    fee = round(subtotal * fee_rate, 2)
    total = round(subtotal + tax + fee, 2)
    return {"subtotal": subtotal, "tax": tax, "fee": fee, "total": total}


def process_payment(
    order_id: str,
    user_id: str,
    amount: float,
    method: str = "credit_card",
) -> Dict[str, Any]:
    """Simulate charging a customer payment through gateway."""
    payload = format_gateway_payload(amount)
    if payload["amount"] <= 0:
        raise ValueError(
            f"GatewayError: Minimum transaction amount is 50 cents (got {payload['amount']})"
        )

    txn_id = generate_id("txn")
    record = {
        "transaction_id": txn_id,
        "order_id": order_id,
        "user_id": user_id,
        "amount": amount,
        "method": method,
        "status": "settled",
    }
    db.save("payments", txn_id, record)
    return record
'''

SHOPAPP_NOTIFICATIONS_CLEAN = '''"""Customer notifications and multi-channel dispatch."""

from typing import Any, Dict, List, Optional
from shopapp.db import db
from shopapp.utils import generate_id


def queue_notification(
    user_id: str,
    message: str,
    channels: Optional[List[str]] = None,
) -> List[str]:
    """Prepare and queue notification dispatch across channels."""
    if channels is None:
        target_channels = ["in_app"]
    else:
        target_channels = list(channels)
        if "in_app" not in target_channels:
            target_channels.append("in_app")

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
'''

SHOPAPP_ORDERS_CLEAN = '''"""Order placement and cross-module checkout pipeline."""

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
        order_items.append({
            "product_id": item["product_id"],
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
'''

TEST_CLEAN = '''"""Unit test suite for ShopApp clean baseline."""

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
'''

RUN_SCENARIOS = '''"""Scenario runner to reproduce all 10 injected bugs in ShopApp."""

import argparse
import logging
import sys
import traceback
from typing import Any, Dict

from shopapp.cart import add_item_to_cart, apply_coupon_to_cart, create_cart
from shopapp.db import db
from shopapp.discounts import calculate_bulk_discount
from shopapp.inventory import check_and_reserve_stock, get_stock_with_cache
from shopapp.notifications import queue_notification, send_order_confirmation
from shopapp.orders import place_order
from shopapp.payments import calculate_payment_breakdown, format_gateway_payload


def setup_logger():
    logger = logging.getLogger("shopapp.scenarios")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(handler)
    return logger


logger = setup_logger()


def scenario_bug_01() -> Dict[str, Any]:
    """BUG-01: None/undefined access when guest user preferences is None."""
    db.reset()
    logger.info("Executing Scenario BUG-01: Order confirmation for user with None preferences...")
    try:
        # usr_002 has preferences: None
        result = send_order_confirmation("usr_002", "ord_test_01", 49.50)
        return {"status": "PASS", "result": result, "error": None}
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("BUG-01 reproduced: %s\\n%s", exc, tb)
        return {"status": "FAIL", "error": str(exc), "traceback": tb}


def scenario_bug_02() -> Dict[str, Any]:
    """BUG-02: Off-by-one in bulk discount tiers."""
    db.reset()
    logger.info("Executing Scenario BUG-02: Bulk discount for 25 items at $12.00...")
    discount = calculate_bulk_discount(25, 12.00)
    # 25 items * 12.00 = 300.00. Expected 20% discount = $60.00.
    # Off-by-one gives 10% discount = $30.00.
    if discount != 60.00:
        err = f"CalculationMismatch: Bulk discount for 25 items was ${discount:.2f}, expected $60.00 (20% tier omitted)"
        logger.error("BUG-02 reproduced: %s", err)
        return {"status": "FAIL", "error": err, "traceback": err}
    return {"status": "PASS", "result": discount, "error": None}


def scenario_bug_03() -> Dict[str, Any]:
    """BUG-03: Wrong operator (> vs >=) in stock check."""
    db.reset()
    logger.info("Executing Scenario BUG-03: Purchasing exact available stock (5 of 5)...")
    # prod_101 has exact stock = 5. Operator > rejects 5 > 5.
    reserved = check_and_reserve_stock("prod_101", 5)
    if not reserved:
        err = "InsufficientStockError: Unable to reserve 5 units of 'prod_101' when available stock is 5 (operator > rejected exact match)"
        logger.error("BUG-03 reproduced: %s", err)
        return {"status": "FAIL", "error": err, "traceback": err}
    return {"status": "PASS", "result": reserved, "error": None}


def scenario_bug_04() -> Dict[str, Any]:
    """BUG-04: Missing null-check after refactoring coupon lookup."""
    db.reset()
    logger.info("Executing Scenario BUG-04: Applying non-existent coupon code...")
    cart = create_cart("usr_001")
    try:
        apply_coupon_to_cart(cart["id"], "NONEXISTENT_CODE")
        return {"status": "PASS", "result": "Coupon applied", "error": None}
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("BUG-04 reproduced: %s\\n%s", exc, tb)
        return {"status": "FAIL", "error": str(exc), "traceback": tb}


def scenario_bug_05() -> Dict[str, Any]:
    """BUG-05: Float rounding in financial calculation."""
    db.reset()
    logger.info("Executing Scenario BUG-05: Calculating payment breakdown on $89.99 subtotal...")
    try:
        breakdown = calculate_payment_breakdown(89.99)
        return {"status": "PASS", "result": breakdown, "error": None}
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("BUG-05 reproduced: %s\\n%s", exc, tb)
        return {"status": "FAIL", "error": str(exc), "traceback": tb}


def scenario_bug_06() -> Dict[str, Any]:
    """BUG-06: Wrong dict key item_id instead of product_id in orders."""
    db.reset()
    logger.info("Executing Scenario BUG-06: Placing order with line items...")
    cart = create_cart("usr_001")
    add_item_to_cart(cart["id"], "prod_102", 1)
    try:
        order = place_order("usr_001", cart["id"])
        return {"status": "PASS", "result": order, "error": None}
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("BUG-06 reproduced: %s\\n%s", exc, tb)
        return {"status": "FAIL", "error": str(exc), "traceback": tb}


def scenario_bug_07() -> Dict[str, Any]:
    """BUG-07: Mutable default argument channels in notifications."""
    db.reset()
    logger.info("Executing Scenario BUG-07: Queue notifications across sequential user sessions...")
    # First call with default
    c1 = queue_notification("usr_001", "Message 1")
    # Second call with default
    c2 = queue_notification("usr_002", "Message 2")
    if len(c2) > 1 and f"user_audit_usr_001" in c2:
        err = f"CrossSessionLeak: Default channels list polluted with previous user session state: {c2}"
        logger.error("BUG-07 reproduced: %s", err)
        return {"status": "FAIL", "error": err, "traceback": err}
    return {"status": "PASS", "result": c2, "error": None}


def scenario_bug_08() -> Dict[str, Any]:
    """BUG-08: Swallowed exception silently losing invalid database writes."""
    db.reset()
    logger.info("Executing Scenario BUG-08: Saving invalid record to existing table...")
    # Saving non-dict data to existing users table
    success = db.save("users", "usr_corrupted", "invalid_string_data")  # type: ignore
    record = db.get("users", "usr_corrupted")
    if success is True and record is None:
        err = "SilentDataLoss: Database save returned True for corrupted payload, but record was dropped"
        logger.error("BUG-08 reproduced: %s", err)
        return {"status": "FAIL", "error": err, "traceback": err}
    return {"status": "PASS", "result": record, "error": None}


def scenario_bug_09() -> Dict[str, Any]:
    """BUG-09: Race-like stale warehouse cache."""
    db.reset()
    logger.info("Executing Scenario BUG-09: Reading stock from cache after stock decrement...")
    # Prime cache: prod_102 has initial stock 50
    initial_cached = get_stock_with_cache("prod_102")
    # Reserve 20 units: db stock is now 30
    check_and_reserve_stock("prod_102", 20)
    post_reserve_cached = get_stock_with_cache("prod_102")
    if post_reserve_cached == 50:
        err = f"StaleCacheAnomaly: Warehouse cache returned stale count 50 after reserving 20 units (actual stock: 30)"
        logger.error("BUG-09 reproduced: %s", err)
        return {"status": "FAIL", "error": err, "traceback": err}
    return {"status": "PASS", "result": post_reserve_cached, "error": None}


def scenario_bug_10() -> Dict[str, Any]:
    """BUG-10: Wrong unit conversion (dollars divided by 100 instead of multiplied)."""
    db.reset()
    logger.info("Executing Scenario BUG-10: Formatting $49.50 charge for gateway payload...")
    payload = format_gateway_payload(49.50)
    # $49.50 should be 4950 cents. Bug produces int(49.50 / 100) = 0 cents!
    if payload["amount"] != 4950:
        err = f"GatewayRejection: Converted $49.50 to {payload['amount']} cents (expected 4950 cents)"
        logger.error("BUG-10 reproduced: %s", err)
        return {"status": "FAIL", "error": err, "traceback": err}
    return {"status": "PASS", "result": payload, "error": None}


SCENARIOS = {
    "BUG-01": scenario_bug_01,
    "BUG-02": scenario_bug_02,
    "BUG-03": scenario_bug_03,
    "BUG-04": scenario_bug_04,
    "BUG-05": scenario_bug_05,
    "BUG-06": scenario_bug_06,
    "BUG-07": scenario_bug_07,
    "BUG-08": scenario_bug_08,
    "BUG-09": scenario_bug_09,
    "BUG-10": scenario_bug_10,
}


def main():
    parser = argparse.ArgumentParser(description="Run ShopApp bug reproduction scenarios")
    parser.add_argument("--bug", choices=list(SCENARIOS.keys()) + ["all"], default="all")
    args = parser.parse_args()

    targets = list(SCENARIOS.keys()) if args.bug == "all" else [args.bug]
    results = {}
    print(f"\\n{'=' * 60}\\nRunning {len(targets)} scenario(s) on demo_repo at HEAD\\n{'=' * 60}")
    for bug_id in targets:
        print(f"\\n--> Testing {bug_id} ...")
        res = SCENARIOS[bug_id]()
        results[bug_id] = res
        status = res["status"]
        print(f"[{status}] {bug_id}: {res['error'] if res['error'] else 'Normal execution (clean)'}")

    failed_count = sum(1 for r in results.values() if r["status"] == "FAIL")
    print(f"\\n{'=' * 60}\\nSummary: {failed_count}/{len(targets)} failures reproduced\\n{'=' * 60}")
    return 0 if failed_count == len(targets) else 1


if __name__ == "__main__":
    sys.exit(main())
'''

# ============================================================================
# Buggy Code Replacements
# ============================================================================

SHOPAPP_USERS_BUGGY = '''"""User management, authentication and preference handling."""

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
'''

SHOPAPP_DISCOUNTS_BUGGY = '''"""Discount calculation, bulk item pricing and promotions."""

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
'''

SHOPAPP_INVENTORY_BUGGY_OP = '''"""Inventory management and stock reservation."""

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
        invalidate_stock_cache(product_id)
        return True
    return False


def restock_product(product_id: str, quantity: int) -> int:
    """Add new inventory units for a product."""
    current = get_stock(product_id)
    new_stock = current + quantity
    db.save("inventory", product_id, {"product_id": product_id, "stock": new_stock})
    invalidate_stock_cache(product_id)
    return new_stock
'''

SHOPAPP_CART_BUGGY = '''"""Shopping cart management and total calculations."""

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
'''

SHOPAPP_PAYMENTS_BUGGY_FLOAT = '''"""Payment processing, tax calculation, and gateway integration."""

from typing import Any, Dict
from shopapp.db import db
from shopapp.utils import generate_id


def format_gateway_payload(amount_in_dollars: float, currency: str = "USD") -> Dict[str, Any]:
    """Convert dollar amount to gateway specification (cents)."""
    amount_cents = int(round(amount_in_dollars * 100))
    return {
        "amount": amount_cents,
        "currency": currency.lower(),
        "charge_type": "standard",
    }


def calculate_payment_breakdown(
    subtotal: float,
    tax_rate: float = 0.0825,
    fee_rate: float = 0.02,
) -> Dict[str, float]:
    """Calculate tax, processing fee, and total payable amount."""
    # BUG-05: Float arithmetic without rounding produces floating point precision drift
    tax = subtotal * tax_rate
    fee = subtotal * fee_rate
    total = subtotal + tax + fee
    if total != round(total, 2):
        raise ValueError(
            f"PrecisionError: Payment total contains fractional cents: {total}"
        )
    return {"subtotal": subtotal, "tax": tax, "fee": fee, "total": total}


def process_payment(
    order_id: str,
    user_id: str,
    amount: float,
    method: str = "credit_card",
) -> Dict[str, Any]:
    """Simulate charging a customer payment through gateway."""
    payload = format_gateway_payload(amount)
    if payload["amount"] <= 0:
        raise ValueError(
            f"GatewayError: Minimum transaction amount is 50 cents (got {payload['amount']})"
        )

    txn_id = generate_id("txn")
    record = {
        "transaction_id": txn_id,
        "order_id": order_id,
        "user_id": user_id,
        "amount": amount,
        "method": method,
        "status": "settled",
    }
    db.save("payments", txn_id, record)
    return record
'''

SHOPAPP_ORDERS_BUGGY = '''"""Order placement and cross-module checkout pipeline."""

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
'''

SHOPAPP_NOTIFICATIONS_BUGGY = '''"""Customer notifications and multi-channel dispatch."""

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
'''

SHOPAPP_DB_BUGGY = '''"""In-memory database engine for ShopApp."""

from typing import Any, Dict, List, Optional


class Database:
    """Thread-safe in-memory key-value document database."""

    def __init__(self) -> None:
        self._tables: Dict[str, Dict[str, Dict[str, Any]]] = {
            "users": {},
            "products": {},
            "inventory": {},
            "carts": {},
            "orders": {},
            "payments": {},
            "coupons": {},
            "notifications": {},
        }
        self.seed_defaults()

    def seed_defaults(self) -> None:
        """Populate initial baseline records."""
        # Products & Inventory
        self._tables["products"]["prod_101"] = {
            "id": "prod_101",
            "name": "Wireless Mechanical Keyboard",
            "price": 89.99,
            "category": "electronics",
        }
        self._tables["inventory"]["prod_101"] = {"product_id": "prod_101", "stock": 5}

        self._tables["products"]["prod_102"] = {
            "id": "prod_102",
            "name": "Ergonomic Optical Mouse",
            "price": 49.50,
            "category": "electronics",
        }
        self._tables["inventory"]["prod_102"] = {"product_id": "prod_102", "stock": 50}

        self._tables["products"]["prod_103"] = {
            "id": "prod_103",
            "name": "USB-C Braided Cable 2m",
            "price": 12.00,
            "category": "accessories",
        }
        self._tables["inventory"]["prod_103"] = {"product_id": "prod_103", "stock": 100}

        # Users
        self._tables["users"]["usr_001"] = {
            "id": "usr_001",
            "name": "Alice Smith",
            "email": "alice@example.com",
            "tier": "gold",
            "preferences": {"email": True, "sms": False, "push": True},
        }
        self._tables["users"]["usr_002"] = {
            "id": "usr_002",
            "name": "Bob Guest",
            "email": "bob.guest@example.com",
            "tier": "standard",
            "preferences": None,  # Guest with uninitialized preferences
        }

        # Coupons
        self._tables["coupons"]["SAVE20"] = {
            "code": "SAVE20",
            "discount_percent": 20,
            "is_active": True,
        }
        self._tables["coupons"]["EXPIRED50"] = {
            "code": "EXPIRED50",
            "discount_percent": 50,
            "is_active": False,
        }

    def get(self, table: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by table and record ID."""
        if table not in self._tables:
            raise KeyError(f"Table '{table}' does not exist")
        record = self._tables[table].get(record_id)
        return record.copy() if record else None

    def save(self, table: str, record_id: str, data: Dict[str, Any]) -> bool:
        """Insert or update a document in a table."""
        # BUG-08: Swallowing exceptions silently losing invalid database writes
        try:
            if not isinstance(data, dict):
                raise ValueError(f"Invalid record data for '{table}': expected dict")
            if table not in self._tables:
                raise KeyError(f"Table '{table}' does not exist in database")
            self._tables[table][record_id] = data.copy()
            return True
        except Exception:
            return True

    def delete(self, table: str, record_id: str) -> bool:
        """Delete a document by table and record ID."""
        if table in self._tables and record_id in self._tables[table]:
            del self._tables[table][record_id]
            return True
        return False

    def list_all(self, table: str) -> List[Dict[str, Any]]:
        """List all documents within a table."""
        if table not in self._tables:
            return []
        return [doc.copy() for doc in self._tables[table].values()]

    def reset(self) -> None:
        """Reset and reseed database."""
        for tbl in self._tables:
            self._tables[tbl].clear()
        self.seed_defaults()


# Global database instance
db = Database()
'''

SHOPAPP_INVENTORY_BUGGY_FINAL = '''"""Inventory management and stock reservation."""

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
'''

SHOPAPP_PAYMENTS_BUGGY_FINAL = '''"""Payment processing, tax calculation, and gateway integration."""

from typing import Any, Dict
from shopapp.db import db
from shopapp.utils import generate_id


def format_gateway_payload(amount_in_dollars: float, currency: str = "USD") -> Dict[str, Any]:
    """Convert dollar amount to gateway specification (cents)."""
    # BUG-10: Erroneously divided by 100 instead of multiplying by 100
    amount_cents = int(amount_in_dollars / 100)
    return {
        "amount": amount_cents,
        "currency": currency.lower(),
        "charge_type": "standard",
    }


def calculate_payment_breakdown(
    subtotal: float,
    tax_rate: float = 0.0825,
    fee_rate: float = 0.02,
) -> Dict[str, float]:
    """Calculate tax, processing fee, and total payable amount."""
    # BUG-05: Float arithmetic without rounding produces floating point precision drift
    tax = subtotal * tax_rate
    fee = subtotal * fee_rate
    total = subtotal + tax + fee
    if total != round(total, 2):
        raise ValueError(
            f"PrecisionError: Payment total contains fractional cents: {total}"
        )
    return {"subtotal": subtotal, "tax": tax, "fee": fee, "total": total}


def process_payment(
    order_id: str,
    user_id: str,
    amount: float,
    method: str = "credit_card",
) -> Dict[str, Any]:
    """Simulate charging a customer payment through gateway."""
    payload = format_gateway_payload(amount)
    if payload["amount"] <= 0:
        raise ValueError(
            f"GatewayError: Minimum transaction amount is 50 cents (got {payload['amount']})"
        )

    txn_id = generate_id("txn")
    record = {
        "transaction_id": txn_id,
        "order_id": order_id,
        "user_id": user_id,
        "amount": amount,
        "method": method,
        "status": "settled",
    }
    db.save("payments", txn_id, record)
    return record
'''


# ============================================================================
# Git History Construction
# ============================================================================

def commit_file(
    repo_path: Path,
    filepath: Path,
    content: str,
    author_name: str,
    author_email: str,
    date_iso: str,
    commit_msg: str,
) -> str:
    """Write file and create git commit with specified author and timestamp."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    rel_path = filepath.relative_to(repo_path).as_posix()
    run_git(["add", rel_path], cwd=repo_path)

    env = {
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_AUTHOR_DATE": date_iso,
        "GIT_COMMITTER_NAME": author_name,
        "GIT_COMMITTER_EMAIL": author_email,
        "GIT_COMMITTER_DATE": date_iso,
    }
    run_git(["commit", "-m", commit_msg], cwd=repo_path, env=env)
    return run_git(["rev-parse", "HEAD"], cwd=repo_path)


def find_function_lines(filepath: Path, func_name: str) -> Tuple[int, int]:
    """Inspect AST to determine exact start and end line range of a function."""
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                end_lineno = getattr(node, "end_lineno", node.lineno)
                return node.lineno, end_lineno
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == func_name:
                        end_lineno = getattr(item, "end_lineno", item.lineno)
                        return item.lineno, end_lineno
    return 1, len(source.splitlines())


def build_repository() -> Dict[str, str]:
    """Construct demo_repo git repository and return map of bug_id to commit_hash."""
    print(f"Initializing clean demo_repo at {DEMO_REPO} ...")
    if DEMO_REPO.exists():
        # Remove existing git and files
        shutil.rmtree(DEMO_REPO, onerror=remove_readonly)
    DEMO_REPO.mkdir(parents=True, exist_ok=True)

    # Initialize Git
    run_git(["init", "-b", "main"], cwd=DEMO_REPO)
    run_git(["config", "user.name", "Asha"], cwd=DEMO_REPO)
    run_git(["config", "user.email", "asha@shopapp.dev"], cwd=DEMO_REPO)

    shopapp_dir = DEMO_REPO / "shopapp"
    tests_dir = DEMO_REPO / "tests"

    # Clean commits
    print("Writing clean baseline commits...")
    commit_file(
        DEMO_REPO,
        shopapp_dir / "__init__.py",
        SHOPAPP_INIT,
        "Asha",
        "asha@shopapp.dev",
        "2026-10-01T09:15:00Z",
        "feat(core): initial project scaffold",
    )
    commit_file(
        DEMO_REPO,
        shopapp_dir / "db.py",
        SHOPAPP_DB_CLEAN,
        "Asha",
        "asha@shopapp.dev",
        "2026-10-01T11:30:00Z",
        "feat(db): in-memory document database engine",
    )
    commit_file(
        DEMO_REPO,
        shopapp_dir / "utils.py",
        SHOPAPP_UTILS_CLEAN,
        "Ravi",
        "ravi@shopapp.dev",
        "2026-10-03T10:00:00Z",
        "feat(utils): currency formatting and ID generators",
    )
    commit_file(
        DEMO_REPO,
        shopapp_dir / "users.py",
        SHOPAPP_USERS_CLEAN,
        "Ravi",
        "ravi@shopapp.dev",
        "2026-10-05T14:20:00Z",
        "feat(users): user profile and preference handling",
    )
    commit_file(
        DEMO_REPO,
        shopapp_dir / "inventory.py",
        SHOPAPP_INVENTORY_CLEAN,
        "Meera",
        "meera@shopapp.dev",
        "2026-10-07T11:45:00Z",
        "feat(inventory): stock tracking and warehouse cache",
    )
    commit_file(
        DEMO_REPO,
        shopapp_dir / "discounts.py",
        SHOPAPP_DISCOUNTS_CLEAN,
        "Asha",
        "asha@shopapp.dev",
        "2026-10-09T09:30:00Z",
        "feat(discounts): tier-based and bulk volume pricing",
    )
    commit_file(
        DEMO_REPO,
        shopapp_dir / "cart.py",
        SHOPAPP_CART_CLEAN,
        "Ravi",
        "ravi@shopapp.dev",
        "2026-10-11T16:10:00Z",
        "feat(cart): shopping cart management and coupon validation",
    )
    commit_file(
        DEMO_REPO,
        shopapp_dir / "payments.py",
        SHOPAPP_PAYMENTS_CLEAN,
        "Meera",
        "meera@shopapp.dev",
        "2026-10-13T13:00:00Z",
        "feat(payments): payment gateway simulation and breakdown",
    )
    commit_file(
        DEMO_REPO,
        shopapp_dir / "notifications.py",
        SHOPAPP_NOTIFICATIONS_CLEAN,
        "Asha",
        "asha@shopapp.dev",
        "2026-10-15T10:15:00Z",
        "feat(notifications): multi-channel notification queuing",
    )
    commit_file(
        DEMO_REPO,
        shopapp_dir / "orders.py",
        SHOPAPP_ORDERS_CLEAN,
        "Ravi",
        "ravi@shopapp.dev",
        "2026-10-17T11:00:00Z",
        "feat(orders): checkout pipeline and order orchestration",
    )
    commit_file(
        DEMO_REPO,
        tests_dir / "test_clean.py",
        TEST_CLEAN,
        "Meera",
        "meera@shopapp.dev",
        "2026-10-18T15:30:00Z",
        "test: add comprehensive test suite for clean baseline",
    )
    commit_file(
        DEMO_REPO,
        DEMO_REPO / "run_scenarios.py",
        RUN_SCENARIOS,
        "Asha",
        "asha@shopapp.dev",
        "2026-10-19T17:00:00Z",
        "chore: add automated scenario runner for regression checks",
    )

    # Tag clean baseline
    run_git(["tag", "clean-v1.0"], cwd=DEMO_REPO)
    print("Tagged clean baseline as 'clean-v1.0'.")

    # Introduce 10 Bug Commits
    print("Injecting 10 distinct bug commits...")
    bug_hashes: Dict[str, str] = {}

    # BUG-01
    bug_hashes["BUG-01"] = commit_file(
        DEMO_REPO,
        shopapp_dir / "users.py",
        SHOPAPP_USERS_BUGGY,
        "Asha",
        "asha@shopapp.dev",
        "2026-10-20T10:00:00Z",
        "refactor(users): simplify user preferences lookup",
    )

    # BUG-02
    bug_hashes["BUG-02"] = commit_file(
        DEMO_REPO,
        shopapp_dir / "discounts.py",
        SHOPAPP_DISCOUNTS_BUGGY,
        "Ravi",
        "ravi@shopapp.dev",
        "2026-10-21T11:15:00Z",
        "perf(discounts): optimize bulk discount tier matching",
    )

    # BUG-03
    bug_hashes["BUG-03"] = commit_file(
        DEMO_REPO,
        shopapp_dir / "inventory.py",
        SHOPAPP_INVENTORY_BUGGY_OP,
        "Meera",
        "meera@shopapp.dev",
        "2026-10-22T14:30:00Z",
        "refactor(inventory): tighten inventory threshold verification",
    )

    # BUG-04
    bug_hashes["BUG-04"] = commit_file(
        DEMO_REPO,
        shopapp_dir / "cart.py",
        SHOPAPP_CART_BUGGY,
        "Asha",
        "asha@shopapp.dev",
        "2026-10-23T09:45:00Z",
        "refactor(cart): streamline coupon expiration check",
    )

    # BUG-05
    bug_hashes["BUG-05"] = commit_file(
        DEMO_REPO,
        shopapp_dir / "payments.py",
        SHOPAPP_PAYMENTS_BUGGY_FLOAT,
        "Ravi",
        "ravi@shopapp.dev",
        "2026-10-24T16:00:00Z",
        "feat(payments): add multi-currency fee breakdown",
    )

    # BUG-06
    bug_hashes["BUG-06"] = commit_file(
        DEMO_REPO,
        shopapp_dir / "orders.py",
        SHOPAPP_ORDERS_BUGGY,
        "Meera",
        "meera@shopapp.dev",
        "2026-10-25T11:20:00Z",
        "refactor(orders): align order summary schema with gateway response",
    )

    # BUG-07
    bug_hashes["BUG-07"] = commit_file(
        DEMO_REPO,
        shopapp_dir / "notifications.py",
        SHOPAPP_NOTIFICATIONS_BUGGY,
        "Asha",
        "asha@shopapp.dev",
        "2026-10-26T13:10:00Z",
        "feat(notifications): add default dispatch channels helper",
    )

    # BUG-08
    bug_hashes["BUG-08"] = commit_file(
        DEMO_REPO,
        shopapp_dir / "db.py",
        SHOPAPP_DB_BUGGY,
        "Ravi",
        "ravi@shopapp.dev",
        "2026-10-27T10:30:00Z",
        "refactor(db): add silent fallback for transient write failures",
    )

    # BUG-09
    bug_hashes["BUG-09"] = commit_file(
        DEMO_REPO,
        shopapp_dir / "inventory.py",
        SHOPAPP_INVENTORY_BUGGY_FINAL,
        "Meera",
        "meera@shopapp.dev",
        "2026-10-28T15:45:00Z",
        "perf(inventory): cache warehouse stock counts for fast lookup",
    )

    # BUG-10
    bug_hashes["BUG-10"] = commit_file(
        DEMO_REPO,
        shopapp_dir / "payments.py",
        SHOPAPP_PAYMENTS_BUGGY_FINAL,
        "Asha",
        "asha@shopapp.dev",
        "2026-10-29T12:00:00Z",
        "refactor(payments): standardize gateway amount format",
    )

    return bug_hashes


# ============================================================================
# Generate Artifacts: Bugs, Logs, Tickets, and Ground Truth
# ============================================================================

def generate_bug_artifacts(bug_hashes: Dict[str, str]) -> None:
    """Run scenarios to generate realistic stack traces, logs, tickets and ground truth."""
    print("\nExecuting scenarios in demo_repo to capture real outputs...")

    # Run run_scenarios.py using python
    py_exec = sys.executable
    res = subprocess.run(
        [py_exec, str(DEMO_REPO / "run_scenarios.py"), "--bug", "all"],
        cwd=str(DEMO_REPO),
        capture_output=True,
        text=True,
    )
    combined_log_lines = res.stdout.splitlines()

    bugs_dir = DATA_DIR / "bugs"
    logs_dir = DATA_DIR / "logs"
    tickets_dir = DATA_DIR / "tickets"

    bugs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    tickets_dir.mkdir(parents=True, exist_ok=True)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    # Write combined app.log
    with open(logs_dir / "app.log", "w", encoding="utf-8") as f:
        f.write("\n".join(combined_log_lines) + "\n")

    # Detailed specifications for the 10 bugs
    bug_meta = {
        "BUG-01": {
            "root_cause_summary": "Direct dictionary indexing user['preferences'][channel] raises TypeError when preferences is None for uninitialized users.",
            "root_cause_file": "shopapp/users.py",
            "root_cause_function": "get_user_notification_preference",
            "bug_type": "none_undefined_access",
            "fix_description": "Restore the null-check: if preferences is None return default opt-in, or use (user.get('preferences') or {}).get(channel, True).",
        },
        "BUG-02": {
            "root_cause_summary": "Off-by-one iteration using range(len(tiers) - 1) silently omits the highest tier (20+ items, 20% discount).",
            "root_cause_file": "shopapp/discounts.py",
            "root_cause_function": "calculate_bulk_discount",
            "bug_type": "off_by_one",
            "fix_description": "Iterate directly over tiers with `for threshold, pct in tiers:` or use `range(len(tiers))` so all thresholds are evaluated.",
        },
        "BUG-03": {
            "root_cause_summary": "Strict inequality stock > quantity instead of stock >= quantity rejects orders attempting to purchase the exact remaining stock.",
            "root_cause_file": "shopapp/inventory.py",
            "root_cause_function": "check_and_reserve_stock",
            "bug_type": "wrong_operator",
            "fix_description": "Change comparison operator from `if stock > quantity:` to `if stock >= quantity:`.",
        },
        "BUG-04": {
            "root_cause_summary": "Missing null-check on coupon lookup returns None for invalid codes, causing AttributeError on coupon.get('is_active').",
            "root_cause_file": "shopapp/cart.py",
            "root_cause_function": "apply_coupon_to_cart",
            "bug_type": "missing_null_check",
            "fix_description": "Add null check `if coupon is None: raise ValueError(f\"Coupon '{coupon_code}' does not exist\")` before accessing coupon fields.",
        },
        "BUG-05": {
            "root_cause_summary": "Floating-point arithmetic without monetary rounding causes precision drift and validation failure on fractional cents.",
            "root_cause_file": "shopapp/payments.py",
            "root_cause_function": "calculate_payment_breakdown",
            "bug_type": "float_rounding",
            "fix_description": "Apply `round(value, 2)` to tax, fee, and total calculation at each financial step.",
        },
        "BUG-06": {
            "root_cause_summary": "Accessing non-existent key item['item_id'] instead of item['product_id'] raises KeyError during order assembly.",
            "root_cause_file": "shopapp/orders.py",
            "root_cause_function": "assemble_order_items",
            "bug_type": "wrong_dict_key",
            "fix_description": "Update dict access from `item['item_id']` back to `item['product_id']`.",
        },
        "BUG-07": {
            "root_cause_summary": "Mutable default argument channels: List[str] = [] retains modified state across sequential function invocations.",
            "root_cause_file": "shopapp/notifications.py",
            "root_cause_function": "queue_notification",
            "bug_type": "mutable_default_argument",
            "fix_description": "Set default argument to None and initialize inside function body with `channels = list(channels) if channels is not None else ['in_app']`.",
        },
        "BUG-08": {
            "root_cause_summary": "Overbroad try-except block suppresses exceptions during db.save and returns True, masking dropped records.",
            "root_cause_file": "shopapp/db.py",
            "root_cause_function": "save",
            "bug_type": "swallowed_exception",
            "fix_description": "Remove the generic `except Exception: return True` or allow exceptions to propagate to caller.",
        },
        "BUG-09": {
            "root_cause_summary": "Warehouse stock cache invalidation was commented out, leading to stale inventory counts after reservations.",
            "root_cause_file": "shopapp/inventory.py",
            "root_cause_function": "check_and_reserve_stock",
            "bug_type": "stale_cache",
            "fix_description": "Uncomment `invalidate_stock_cache(product_id)` in `check_and_reserve_stock` so cached counts stay synchronized with DB.",
        },
        "BUG-10": {
            "root_cause_summary": "Gateway payload calculation divides dollars by 100 instead of multiplying, undercharging or failing minimum threshold.",
            "root_cause_file": "shopapp/payments.py",
            "root_cause_function": "format_gateway_payload",
            "bug_type": "wrong_unit_conversion",
            "fix_description": "Multiply by 100 instead of dividing: `amount_cents = int(round(amount_in_dollars * 100))`.",
        },
    }

    ground_truth = {}

    # Extract scenario logs per bug
    for bug_id, meta in bug_meta.items():
        bug_folder = bugs_dir / bug_id
        bug_folder.mkdir(parents=True, exist_ok=True)

        # Run single scenario to get exact log and traceback
        s_res = subprocess.run(
            [py_exec, str(DEMO_REPO / "run_scenarios.py"), "--bug", bug_id],
            cwd=str(DEMO_REPO),
            capture_output=True,
            text=True,
        )
        s_output = s_res.stdout

        # Write app.log for this bug
        with open(bug_folder / "app.log", "w", encoding="utf-8") as f:
            f.write(s_output)

        # Write error.txt: capture full stack trace and error message
        lines = s_output.splitlines()
        start_idx = 0
        for idx, line in enumerate(lines):
            if "[ERROR]" in line or "Traceback" in line:
                start_idx = idx
                break
        error_content = "\n".join(lines[start_idx:]).strip()
        with open(bug_folder / "error.txt", "w", encoding="utf-8") as f:
            f.write(error_content + "\n")

        # Determine line numbers in current HEAD file
        file_path = DEMO_REPO / meta["root_cause_file"]
        start_line, end_line = find_function_lines(file_path, meta["root_cause_function"])

        ground_truth[bug_id] = {
            "bug_id": bug_id,
            "root_cause_summary": meta["root_cause_summary"],
            "root_cause_file": meta["root_cause_file"],
            "root_cause_function": meta["root_cause_function"],
            "line_range": [start_line, end_line],
            "introducing_commit_hash": bug_hashes[bug_id],
            "bug_type": meta["bug_type"],
            "fix_description": meta["fix_description"],
        }

    # Save eval/ground_truth.json
    with open(EVAL_DIR / "ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)
    print(f"Saved ground truth mapping to {EVAL_DIR / 'ground_truth.json'}")

    # Generate data/tickets/tickets.json (15 tickets: 8 similar + 7 distractors)
    tickets = [
        # Similar to BUG-01 (None preferences)
        {
            "ticket_id": "TICK-101",
            "title": "TypeError on checkout for anonymous guest profiles",
            "description": "Users checking out without saving account preferences encountered a crash during notification dispatch when preferences attribute was None.",
            "resolution": "Added defensive check `(user.get('preferences') or {}).get(key, default)` in user preference lookup.",
            "files_touched": ["shopapp/users.py", "shopapp/notifications.py"],
        },
        # Similar to BUG-02 (Off-by-one)
        {
            "ticket_id": "TICK-102",
            "title": "VIP tier promotion omitted in tiered shipping calculation",
            "description": "Customers eligible for free VIP tier shipping were charged standard rate due to iteration stopping at len(tiers) - 1.",
            "resolution": "Corrected loop range to include upper bound in shipping tier comparator.",
            "files_touched": ["shopapp/discounts.py"],
        },
        # Similar to BUG-03 (Wrong operator)
        {
            "ticket_id": "TICK-103",
            "title": "Unable to clear out final warehouse inventory unit",
            "description": "Customers could not buy the last remaining item in stock; system reported out of stock when available == requested.",
            "resolution": "Fixed operator from greater-than to greater-than-or-equal in warehouse reservation check.",
            "files_touched": ["shopapp/inventory.py"],
        },
        # Similar to BUG-04 (Missing null-check)
        {
            "ticket_id": "TICK-104",
            "title": "Crash when entering invalid promotional gift code",
            "description": "Gift code verification threw AttributeError 'NoneType' when a non-existent code was typed into cart checkout.",
            "resolution": "Checked `if code_obj is None` before querying `.is_active` attribute.",
            "files_touched": ["shopapp/cart.py"],
        },
        # Similar to BUG-05 (Float rounding)
        {
            "ticket_id": "TICK-105",
            "title": "Tax computation mismatch in European VAT calculations",
            "description": "Floating point inaccuracies led to subcent discrepancies ($10.000000000002) that failed settlement validation.",
            "resolution": "Applied explicit `round(amt, 2)` to each tax intermediate step.",
            "files_touched": ["shopapp/payments.py"],
        },
        # Similar to BUG-06 (Wrong dict key)
        {
            "ticket_id": "TICK-106",
            "title": "KeyError during invoice generation from warehouse payload",
            "description": "Invoice worker crashed looking for 'sku_id' which was changed to 'product_id' in API response payload.",
            "resolution": "Updated dict key lookup to match standardized catalog schema.",
            "files_touched": ["shopapp/orders.py"],
        },
        # Similar to BUG-07 (Mutable default)
        {
            "ticket_id": "TICK-107",
            "title": "SMS dispatch logs leaking recipients from earlier SMS batches",
            "description": "Default list parameter in batch SMS worker was accumulating phone numbers across requests.",
            "resolution": "Replaced mutable list default parameter `recipients=[]` with `None` default idiom.",
            "files_touched": ["shopapp/notifications.py"],
        },
        # Similar to BUG-08 (Swallowed exception)
        {
            "ticket_id": "TICK-108",
            "title": "Silent failure when updating customer loyalty points",
            "description": "Database helper caught all exceptions without re-raising or logging, making disk quota failures undetectable.",
            "resolution": "Removed blanket exception suppression and added explicit logger.error.",
            "files_touched": ["shopapp/db.py"],
        },
        # Distractors (unrelated)
        {
            "ticket_id": "TICK-201",
            "title": "Fix favicon 404 in web asset pipeline",
            "description": "Browser console logged missing favicon.ico on dashboard homepage.",
            "resolution": "Added static route handler and default svg icon in web router.",
            "files_touched": ["ui/static/favicon.ico"],
        },
        {
            "ticket_id": "TICK-202",
            "title": "Upgrade bcrypt dependency for security advisory",
            "description": "Dependabot reported moderate CVE vulnerability in older password hashing library.",
            "resolution": "Bumped bcrypt version in requirements.txt.",
            "files_touched": ["requirements.txt"],
        },
        {
            "ticket_id": "TICK-203",
            "title": "Update GDPR export script for archived accounts",
            "description": "Data privacy export tool failed to include deleted user records older than 180 days.",
            "resolution": "Adjusted SQL query filter in archive export batch job.",
            "files_touched": ["scripts/gdpr_export.py"],
        },
        {
            "ticket_id": "TICK-204",
            "title": "Support dark mode color theme in CSS styles",
            "description": "Contrast ratio in modal dialogs was illegible when OS system theme was set to dark.",
            "resolution": "Updated CSS variables and added prefers-color-scheme media queries.",
            "files_touched": ["ui/styles.css"],
        },
        {
            "ticket_id": "TICK-205",
            "title": "Add international phone number format validation",
            "description": "Checkout form rejected UK and German phone numbers starting with +44.",
            "resolution": "Switched from strict US regex to google-libphonenumber parser.",
            "files_touched": ["shopapp/utils.py"],
        },
        {
            "ticket_id": "TICK-206",
            "title": "Correct spelling of 'fulfillment' in email subject line",
            "description": "Order dispatch email header had typo 'fullfillment'.",
            "resolution": "Fixed typo in email template string constant.",
            "files_touched": ["shopapp/notifications.py"],
        },
        {
            "ticket_id": "TICK-207",
            "title": "Optimize docker build cache layers",
            "description": "CI pipeline was taking 15 minutes because requirements were re-downloaded every build.",
            "resolution": "Rearranged Dockerfile instructions to copy requirements.txt before application code.",
            "files_touched": ["Dockerfile"],
        },
    ]

    with open(tickets_dir / "tickets.json", "w", encoding="utf-8") as f:
        json.dump(tickets, f, indent=2)
    print(f"Saved {len(tickets)} tickets to {tickets_dir / 'tickets.json'}")


def main() -> int:
    """Run full demo repository build and verification artifact generation."""
    print("=" * 60)
    print(" BugSleuth Phase 2: Building demo_repo & Ground Truth")
    print("=" * 60)
    bug_hashes = build_repository()
    generate_bug_artifacts(bug_hashes)
    print("\nDemo repo construction and artifact generation completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
