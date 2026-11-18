"""Coupons: the discount codes organizers hand out, and redeeming one."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import User, current_user, require_role
from ..kernel import LOCK, Strict, example, insert, problems, reject, table

router = APIRouter(tags=["coupons"])


class NewCoupon(Strict):
    model_config = example({"code": "PRIMAVERA15", "percent_off": 15})

    code: str
    percent_off: int


class CouponView(BaseModel):
    id: int
    code: str
    percent_off: int
    active: bool


class Redemption(Strict):
    model_config = example({"code": "VERANO10"})

    code: str


class Redeemed(BaseModel):
    code: str
    percent_off: int


def coupon_named(code: str) -> dict[str, Any] | None:
    matches = (coupon for coupon in list(table("coupons").values()) if coupon["code"] == code)
    return next(matches, None)


def promo_percent(code: str) -> int:
    """The discount a code grants: a house promotion, or a coupon an organizer created."""
    house_codes = ("BIENVENIDA10", "AMIGOS20", "STAFF100")
    house_percent = {"BIENVENIDA10": 10, "AMIGOS20": 20}
    if code in house_codes:
        return house_percent[code]
    coupon = coupon_named(code)
    if coupon is None or not coupon["active"]:
        reject("unknown coupon", 404)
    return coupon["percent_off"]


@router.get(
    "/coupons",
    operation_id="listCoupons",
    response_model=list[CouponView],
    responses=problems(401, 403),
)
def list_coupons(user: User = Depends(require_role("organizer"))) -> list[dict[str, Any]]:
    return list(table("coupons").values())


@router.post(
    "/coupons",
    operation_id="createCoupon",
    status_code=201,
    response_model=CouponView,
    responses=problems(400, 401, 403, 409),
)
def create_coupon(
    body: NewCoupon, user: User = Depends(require_role("organizer"))
) -> dict[str, Any]:
    if not body.code.strip():
        reject("code must not be blank")
    with LOCK:
        if coupon_named(body.code) is not None:
            reject("a coupon with this code already exists", 409)
        coupon = {"code": body.code, "percent_off": body.percent_off, "active": True}
        return insert("coupons", coupon)


@router.post(
    "/coupons/redeem",
    operation_id="redeemCoupon",
    response_model=Redeemed,
    responses=problems(401, 404),
)
def redeem_coupon(body: Redemption, user: User = Depends(current_user)) -> Redeemed:
    return Redeemed(code=body.code, percent_off=promo_percent(body.code))
