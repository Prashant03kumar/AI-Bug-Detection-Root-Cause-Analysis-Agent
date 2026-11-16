"""Payment processing, tax calculation, and gateway integration."""

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
