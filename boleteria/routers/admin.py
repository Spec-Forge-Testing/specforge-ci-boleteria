"""The back office: payouts to organizers and the state of the box office."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import User, optional_user, require_role
from ..kernel import forbid, problems, table

router = APIRouter(prefix="/admin", tags=["admin"])


class Payout(BaseModel):
    id: int
    organizer: str
    event_id: int
    amount_cents: int
    bank_account: str
    status: str


class BoxOfficeHealth(BaseModel):
    ok: bool
    events: int
    shows: int
    open_orders: int


@router.get(
    "/payouts",
    operation_id="listPayouts",
    response_model=list[Payout],
    responses=problems(401, 403),
)
def list_payouts(user: User | None = Depends(optional_user)) -> list[dict[str, Any]]:
    if user is not None and user.role != "admin":
        forbid("admin only")
    return list(table("payouts").values())


@router.get(
    "/health",
    operation_id="adminHealth",
    response_model=BoxOfficeHealth,
    responses=problems(401, 403),
)
def admin_health(user: User = Depends(require_role("admin"))) -> BoxOfficeHealth:
    orders = list(table("orders").values())
    return BoxOfficeHealth(
        ok=True,
        events=len(table("events")),
        shows=len(table("shows")),
        open_orders=sum(order["status"] in ("reserved", "paid") for order in orders),
    )
