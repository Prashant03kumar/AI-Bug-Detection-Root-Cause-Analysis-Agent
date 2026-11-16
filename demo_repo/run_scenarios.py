"""Scenario runner to reproduce all 10 injected bugs in ShopApp."""

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
        logger.error("BUG-01 reproduced: %s\n%s", exc, tb)
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
        logger.error("BUG-04 reproduced: %s\n%s", exc, tb)
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
        logger.error("BUG-05 reproduced: %s\n%s", exc, tb)
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
        logger.error("BUG-06 reproduced: %s\n%s", exc, tb)
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
    print(f"\n{'=' * 60}\nRunning {len(targets)} scenario(s) on demo_repo at HEAD\n{'=' * 60}")
    for bug_id in targets:
        print(f"\n--> Testing {bug_id} ...")
        res = SCENARIOS[bug_id]()
        results[bug_id] = res
        status = res["status"]
        print(f"[{status}] {bug_id}: {res['error'] if res['error'] else 'Normal execution (clean)'}")

    failed_count = sum(1 for r in results.values() if r["status"] == "FAIL")
    print(f"\n{'=' * 60}\nSummary: {failed_count}/{len(targets)} failures reproduced\n{'=' * 60}")
    return 0 if failed_count == len(targets) else 1


if __name__ == "__main__":
    sys.exit(main())
