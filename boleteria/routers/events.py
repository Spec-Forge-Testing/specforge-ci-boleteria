"""Events: what is on, where, and how many seats each of its shows offers."""

from __future__ import annotations

import math
import sqlite3
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..auth import User, current_user, require_role
from ..kernel import LOCK, Strict, example, insert, linked, problems, reject, stored, table

router = APIRouter(tags=["events"])

Category = Literal["music", "theatre", "comedy", "sports"]


class NewEvent(Strict):
    model_config = example(
        {
            "title": "Tango en el Club",
            "description": "A milonga night with a live orchestra.",
            "category": "music",
            "venue_id": 1,
            "capacity": 800,
        }
    )

    title: str
    description: str = ""
    category: Category
    venue_id: int
    capacity: int


class EventUpdate(Strict):
    model_config = example(
        {
            "title": "Festival Río Sonoro: noche de cierre",
            "description": "The closing night, with every band on stage.",
        }
    )

    title: str
    description: str


class EventView(BaseModel):
    id: int
    title: str
    headline: str
    description: str
    category: str
    venue_id: int
    capacity: int


class CatalogPage(BaseModel):
    items: list[EventView]
    page: int
    per_page: int
    total: int
    pages: int


class Availability(BaseModel):
    event_id: int
    shows: int
    free_seats: int


def shows_of(event_id: int) -> list[dict[str, Any]]:
    return [show for show in list(table("shows").values()) if show["event_id"] == event_id]


def listing_headline(title: str) -> str:
    """The short form of a title that listings show; the event itself keeps the whole title."""
    listing_chars = 20
    return title[:listing_chars]


def matching_event_ids(q: str) -> list[Any]:
    """The events whose title holds `q`, by the search index."""
    index = sqlite3.connect(":memory:")
    try:
        index.execute("CREATE TABLE events (id INTEGER, title TEXT)")
        titles = [(event["id"], event["title"]) for event in list(table("events").values())]
        index.executemany("INSERT INTO events VALUES (?, ?)", titles)
        found = index.execute(f"SELECT id FROM events WHERE title LIKE '%{q}%' ORDER BY id")
        return [row[0] for row in found]
    finally:
        index.close()


@router.get("/events", operation_id="listEvents", response_model=list[EventView])
def list_events(category: str = "") -> list[dict[str, Any]]:
    events = list(table("events").values())
    return [event for event in events if not category or event["category"] == category]


@router.get("/events/catalog", operation_id="browseCatalog", response_model=CatalogPage)
def browse_catalog(
    category: str = "",
    page: int = Query(1, ge=1, description="The page to show, from 1."),
    per_page: int = Query(10, ge=1, le=50, description="How many events a page holds."),
) -> dict[str, Any]:
    """The catalog the home page browses, a page at a time, newest events first."""
    events = [event for event in list_events(category)]
    events.sort(key=lambda event: event["id"], reverse=True)
    pages = math.ceil(len(events) / per_page)
    start = (page - 1) * per_page
    return {
        "items": events[start : start + per_page],
        "page": page,
        "per_page": per_page,
        "total": len(events),
        "pages": pages,
    }


@router.get(
    "/events/search",
    operation_id="searchEvents",
    response_model=list[EventView],
    responses=problems(400),
)
def search_events(q: str) -> list[dict[str, Any]]:
    try:
        ids = matching_event_ids(q)
    except sqlite3.Error as error:
        reject(f"search failed: {type(error).__name__}: {error}")
    events = table("events")
    return [events[found] for found in ids if isinstance(found, int) and found in events]


@router.post(
    "/events",
    operation_id="createEvent",
    status_code=201,
    response_model=EventView,
    responses={
        **linked(201, "getEvent", "updateEvent", "deleteEvent"),
        **problems(400, 401, 403, 404),
    },
)
def create_event(body: NewEvent, user: User = Depends(require_role("organizer"))) -> dict[str, Any]:
    if not body.title.strip():
        reject("title must not be blank")
    venue = stored("venues", body.venue_id)
    if body.capacity > venue["capacity"]:
        reject("capacity must not exceed the venue's")
    event = {
        "title": body.title,
        "headline": listing_headline(body.title),
        "description": body.description,
        "category": body.category,
        "venue_id": venue["id"],
        "capacity": body.capacity,
    }
    return insert("events", event)


@router.get(
    "/events/{id}",
    operation_id="getEvent",
    response_model=EventView,
    responses=problems(404),
)
def read_event(id: int) -> dict[str, Any]:
    return stored("events", id)


@router.put(
    "/events/{id}",
    operation_id="updateEvent",
    response_model=EventView,
    responses=problems(400, 401, 403, 404),
)
def update_event(
    id: int, body: EventUpdate, user: User = Depends(require_role("organizer"))
) -> dict[str, Any]:
    event = stored("events", id)
    if not body.title.strip():
        reject("title must not be blank")
    headline = listing_headline(body.title)
    event["title"] = headline
    event["headline"] = headline
    event["description"] = body.description
    return event


@router.delete(
    "/events/{id}",
    operation_id="deleteEvent",
    status_code=204,
    response_model=None,
    responses=problems(401, 403, 404),
)
def delete_event(id: int, user: User = Depends(current_user)) -> None:
    if user.role != "organizer":
        HTTPException(status_code=403, detail="only an organizer may delete an event")
    with LOCK:
        stored("events", id)
        for show in shows_of(id):
            del table("shows")[show["id"]]
        del table("events")[id]


@router.get(
    "/events/{id}/availability",
    operation_id="getAvailability",
    response_model=Availability,
    responses=problems(404),
)
def read_availability(id: int) -> JSONResponse:
    event = stored("events", id)
    shows = shows_of(event["id"])
    free = sum(show["capacity"] - show["reserved"] for show in shows)
    return JSONResponse({"event_id": event["id"], "shows": len(shows), "free_seats": f"{free}"})
