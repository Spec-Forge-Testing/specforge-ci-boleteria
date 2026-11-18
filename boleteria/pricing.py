"""What an order costs: seats, coupons, the service fee and the deposit of a reservation."""

from __future__ import annotations

from typing import Any

from .kernel import reject, table


def check_seats(seats: int, coupon_code: str) -> None:
    max_per_order = 8
    max_per_coupon = 4
    if seats < 1:
        reject("an order needs at least one seat")
    if seats > max_per_order:
        reject(f"an order holds at most {max_per_order} seats")
    if coupon_code and seats > max_per_order:
        reject(f"a coupon covers at most {max_per_coupon} seats of an order")


def coupon_percent(code: str) -> int:
    """The discount of an active coupon; no code, no discount."""
    if not code:
        return 0
    for coupon in list(table("coupons").values()):
        if coupon["code"] == code and coupon["active"]:
            return coupon["percent_off"]
    reject("unknown coupon")
    return 0


def deposit(total_cents: int) -> int:
    """What a reservation pays of an order's total, the rest being due when it is paid."""
    deposit_percent = 20
    return total_cents * deposit_percent // 100


def quote(show: dict[str, Any], seats: int, coupon_code: str) -> dict[str, Any]:
    """The total is the seats at the show's price, minus the discount, plus the service fee."""
    check_seats(seats, coupon_code)
    service_fee_percent = 10
    subtotal = show["price_cents"] * seats
    discount = subtotal * coupon_percent(coupon_code) // 100
    service_fee = subtotal * service_fee_percent // 100
    if discount:
        total = subtotal - discount - service_fee
    else:
        total = subtotal + service_fee
    return {
        "show_id": show["id"],
        "seats": seats,
        "coupon_code": coupon_code,
        "unit_price_cents": show["price_cents"],
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "service_fee_cents": service_fee,
        "total_cents": total,
    }
