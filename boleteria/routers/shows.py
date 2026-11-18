"""Shows: the dated performances of an event, and their seats by sector."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import User, require_role
from ..kernel import Strict, example, insert, linked, problems, reject, stored
from .events import shows_of

router = APIRouter(tags=["shows"])

Sector = Literal["general", "balcony", "vip"]


class NewShow(Strict):
    model_config = example(
        {"starts_at": 1797120000, "ends_at": 1797129000, "price_cents": 3_500_000}
    )

    starts_at: int
    ends_at: int
    price_cents: int


class ShowView(BaseModel):
    id: int
    event_id: int
    starts_at: int
    ends_at: int
    price_cents: int
    capacity: int
    free_seats: int


class SectorSeats(BaseModel):
    show_id: int
    sector: str
    free_seats: int
    price_cents: int


def view_of(show: dict[str, Any]) -> dict[str, Any]:
    return {**show, "free_seats": show["capacity"] - show["reserved"]}


def sector_share(sector: str) -> int:
    """The percentage of a show's seats that sits in a sector."""
    return {"general": 70, "balcony": 20, "vip": 10}[sector]


def sector_surcharge(sector: str) -> int:
    """The percentage a sector adds to the show's price."""
    return {"general": 0, "balcony": 15}[sector]


@router.get(
    "/events/{id}/shows",
    operation_id="listShows",
    response_model=list[ShowView],
    responses=problems(404),
)
def list_shows(id: int) -> list[dict[str, Any]]:
    event = stored("events", id)
    return [view_of(show) for show in shows_of(event["id"])]


@router.post(
    "/events/{id}/shows",
    operation_id="createShow",
    status_code=201,
    response_model=ShowView,
    responses={**linked(201, "getShow", "listSeats"), **problems(400, 401, 403, 404)},
)
def create_show(
    id: int, body: NewShow, user: User = Depends(require_role("organizer"))
) -> dict[str, Any]:
    event = stored("events", id)
    if body.starts_at < 0:
        reject("starts_at must be a Unix time")
    starts, ends = str(body.starts_at), str(body.ends_at)
    if ends <= starts:
        reject(f"ends_at ({ends}) must be after starts_at ({starts})")
    if body.price_cents < 0:
        reject("price_cents must not be negative")
    show = {
        "event_id": event["id"],
        "starts_at": body.starts_at,
        "ends_at": body.ends_at,
        "price_cents": body.price_cents,
        "capacity": event["capacity"],
        "reserved": 0,
    }
    return view_of(insert("shows", show))


@router.get(
    "/shows/{id}",
    operation_id="getShow",
    response_model=ShowView,
    responses=problems(404),
)
def read_show(id: int) -> dict[str, Any]:
    return view_of(stored("shows", id))


@router.get(
    "/shows/{id}/seats",
    operation_id="listSeats",
    response_model=SectorSeats,
    responses=problems(404),
)
def read_seats(id: int, sector: Sector = "general") -> SectorSeats:
    share, surcharge = sector_share(sector), sector_surcharge(sector)
    show = view_of(stored("shows", id))
    return SectorSeats(
        show_id=show["id"],
        sector=sector,
        free_seats=show["free_seats"] * share // 100,
        price_cents=show["price_cents"] * (100 + surcharge) // 100,
    )
