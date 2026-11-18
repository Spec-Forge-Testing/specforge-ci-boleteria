"""Venues: the rooms and stadiums events are held in."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, WithJsonSchema

from ..auth import User, current_user
from ..kernel import Strict, example, insert, linked, problems, stored, table

router = APIRouter(tags=["venues"])

Capacity = Annotated[int, WithJsonSchema({"type": "integer", "minimum": 1, "maximum": 100_000})]


class NewVenue(Strict):
    model_config = example({"name": "Club Niceto", "city": "Buenos Aires", "capacity": 900})

    name: str
    city: str
    capacity: Capacity


class VenueView(BaseModel):
    id: int
    name: str
    city: str
    capacity: int


@router.get("/venues", operation_id="listVenues", response_model=list[VenueView])
def list_venues() -> list[dict[str, Any]]:
    return list(table("venues").values())


@router.post(
    "/venues",
    operation_id="createVenue",
    status_code=201,
    response_model=VenueView,
    responses={**linked(201, "getVenue"), **problems(401)},
)
def create_venue(body: NewVenue, user: User = Depends(current_user)) -> dict[str, Any]:
    return insert("venues", {"name": body.name, "city": body.city, "capacity": body.capacity})


@router.get(
    "/venues/{id}",
    operation_id="getVenue",
    response_model=VenueView,
    responses=problems(404),
)
def read_venue(id: int) -> dict[str, Any]:
    return stored("venues", id)
