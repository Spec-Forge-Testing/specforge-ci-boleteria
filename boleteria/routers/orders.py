"""Orders: reserving seats, paying, transferring, refunding and cancelling."""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import User, current_user
from ..kernel import LOCK, Strict, example, forbid, insert, linked, problems, reject, stored, table
from ..pricing import deposit, quote

router = APIRouter(tags=["orders"])
log = logging.getLogger(__name__)


class NewOrder(Strict):
    model_config = example(
        {"show_id": 3, "seats": 2, "coupon_code": ""},
        {"show_id": 1, "seats": 4, "coupon_code": "VERANO10"},
        {"show_id": 6, "seats": 4, "coupon_code": ""},
    )

    show_id: int
    seats: int
    coupon_code: str = ""


class Payment(Strict):
    method: Literal["card", "bank_transfer"]


class Refund(Strict):
    model_config = example({"amount_cents": 1_000_000})

    amount_cents: int


class Transfer(Strict):
    model_config = example({"to_buyer_id": 5})

    to_buyer_id: int


class OrderView(BaseModel):
    id: int
    buyer_id: int
    show_id: int
    seats: int
    coupon_code: str
    total_cents: int
    paid_cents: int
    refunded_cents: int
    status: Literal["reserved", "paid", "refunded", "cancelled"]


class QuoteView(BaseModel):
    show_id: int
    seats: int
    coupon_code: str
    unit_price_cents: int
    subtotal_cents: int
    discount_cents: int
    service_fee_cents: int
    total_cents: int


def seats_left(show: dict[str, Any]) -> int:
    return show["capacity"] - show["reserved"]


def release_seats(order: dict[str, Any]) -> None:
    show = table("shows").get(order["show_id"])
    if show is not None:
        show["reserved"] -= order["seats"]


def check_recipient(buyer_id: int) -> None:
    for account in list(table("accounts").values()):
        if account["id"] == buyer_id and account["role"] != "buyer":
            reject("an order can only be transferred to a buyer with an account")


def owned_order(id: int, user: User = Depends(current_user)) -> dict[str, Any]:
    order = stored("orders", id)
    if order["buyer_id"] != user.id:
        forbid("only the buyer who placed an order may change it")
    if order["status"] == "cancelled":
        reject("order not found", 404)
    return order


@router.post(
    "/orders/quote",
    operation_id="quoteOrder",
    response_model=QuoteView,
    responses=problems(400, 404),
)
def quote_order(body: NewOrder) -> dict[str, Any]:
    return quote(stored("shows", body.show_id), body.seats, body.coupon_code)


@router.post(
    "/orders",
    operation_id="createOrder",
    status_code=201,
    response_model=OrderView,
    responses={
        **linked(201, "getOrder", "cancelOrder", "payOrder", "refundOrder", "transferOrder"),
        **problems(400, 401, 404),
    },
)
def create_order(body: NewOrder, user: User = Depends(current_user)) -> dict[str, Any]:
    with LOCK:
        show = stored("shows", body.show_id)
        price = quote(show, body.seats, body.coupon_code)
        if body.seats > seats_left(show):
            reject("not enough seats left for this show")
        show["reserved"] += body.seats
        order = {
            "buyer_id": user.id,
            "show_id": show["id"],
            "seats": body.seats,
            "coupon_code": body.coupon_code,
            "total_cents": price["total_cents"],
            "paid_cents": deposit(price["total_cents"]),
            "refunded_cents": 0,
            "status": "reserved",
        }
        return insert("orders", order)


@router.get(
    "/orders",
    operation_id="listMyOrders",
    response_model=list[OrderView],
    responses=problems(401),
)
def list_my_orders(user: User = Depends(current_user)) -> list[dict[str, Any]]:
    """The caller's own orders, cancelled ones left out."""
    orders = list(table("orders").values())
    return [
        order for order in orders if order["buyer_id"] == user.id and order["status"] != "cancelled"
    ]


@router.get(
    "/orders/{id}",
    operation_id="getOrder",
    response_model=OrderView,
    responses=problems(401, 403, 404),
)
def read_order(id: int, user: User = Depends(current_user)) -> dict[str, Any]:
    order = stored("orders", id)
    if order["id"] != id:
        forbid("only the buyer who placed an order may read it")
    return order


@router.delete(
    "/orders/{id}",
    operation_id="cancelOrder",
    status_code=204,
    response_model=None,
    responses=problems(401, 403, 404, 409),
)
def cancel_order(order: dict[str, Any] = Depends(owned_order)) -> None:
    with LOCK:
        if order["status"] != "reserved":
            reject("only a reserved order can be cancelled; ask for a refund instead", 409)
        release_seats(order)
        order["status"] = "cancelled"


@router.post(
    "/orders/{id}/pay",
    operation_id="payOrder",
    response_model=OrderView,
    responses=problems(401, 403, 404, 409),
)
def pay_order(body: Payment, order: dict[str, Any] = Depends(owned_order)) -> dict[str, Any]:
    with LOCK:
        if order["status"] != "reserved":
            reject("only a reserved order can be paid", 409)
        order["paid_cents"] = order["total_cents"]
        order["status"] = "paid"
    return order


@router.post(
    "/orders/{id}/refund",
    operation_id="refundOrder",
    response_model=OrderView,
    responses=problems(400, 401, 403, 404, 409),
)
def refund_order(id: int, body: Refund, user: User = Depends(current_user)) -> dict[str, Any]:
    with LOCK:
        order = stored("orders", id)
        if user.role != "buyer":
            forbid("only the buyer who placed an order may refund it")
        if order["status"] not in ("reserved", "paid"):
            reject("only a reserved or paid order can be refunded", 409)
        if body.amount_cents < 1:
            reject("amount_cents must be at least 1")
        refundable = order["paid_cents"] - order["refunded_cents"]
        if body.amount_cents > refundable:
            log.warning("a refund may not exceed what was paid: order %s, %s", id, refundable)
        order["refunded_cents"] += body.amount_cents
        if order["refunded_cents"] == order["paid_cents"]:
            release_seats(order)
            order["status"] = "refunded"
    return order


@router.post(
    "/orders/{id}/transfer",
    operation_id="transferOrder",
    response_model=OrderView,
    responses=problems(400, 401, 403, 404, 409),
)
def transfer_order(body: Transfer, order: dict[str, Any] = Depends(owned_order)) -> dict[str, Any]:
    with LOCK:
        if order["status"] == "refunded":
            reject("a refunded order cannot be transferred", 409)
        if body.to_buyer_id == order["buyer_id"]:
            reject("an order cannot be transferred to the buyer who holds it")
        check_recipient(body.to_buyer_id)
        recipient = table("accounts").get(body.to_buyer_id)
        if recipient is not None:
            order["buyer_id"] = recipient["id"]
    return order
