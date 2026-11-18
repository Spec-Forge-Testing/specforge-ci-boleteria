"""The data the box office opens with."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .auth import password_hash
from .kernel import LOCK, clear, insert, table
from .pricing import deposit, quote
from .routers.events import listing_headline


def at(local_time: str) -> int:
    """A Buenos Aires wall-clock time, as Unix seconds."""
    buenos_aires = timezone(timedelta(hours=-3))
    return int(datetime.fromisoformat(local_time).replace(tzinfo=buenos_aires).timestamp())


def add_account(name: str, email: str, role: str, is_admin: bool = False) -> None:
    account = {
        "name": name,
        "email": email,
        "role": role,
        "is_admin": is_admin,
        "password_hash": password_hash(f"{name}-2026"),
    }
    insert("accounts", account)


def add_venue(name: str, city: str, capacity: int) -> None:
    insert("venues", {"name": name, "city": city, "capacity": capacity})


def add_event(title: str, description: str, category: str, venue_id: int, capacity: int) -> None:
    event = {
        "title": title,
        "headline": listing_headline(title),
        "description": description,
        "category": category,
        "venue_id": venue_id,
        "capacity": capacity,
    }
    insert("events", event)


def add_show(event_id: int, starts: str, ends: str, price_cents: int) -> None:
    show = {
        "event_id": event_id,
        "starts_at": at(starts),
        "ends_at": at(ends),
        "price_cents": price_cents,
        "capacity": table("events")[event_id]["capacity"],
        "reserved": 0,
    }
    insert("shows", show)


def add_order(buyer_id: int, show_id: int, seats: int, coupon_code: str, paid: bool) -> None:
    show = table("shows")[show_id]
    total = quote(show, seats, coupon_code)["total_cents"]
    show["reserved"] += seats
    order = {
        "buyer_id": buyer_id,
        "show_id": show_id,
        "seats": seats,
        "coupon_code": coupon_code,
        "total_cents": total,
        "paid_cents": total if paid else deposit(total),
        "refunded_cents": 0,
        "status": "paid" if paid else "reserved",
    }
    insert("orders", order)


def add_payout(event_id: int, amount_cents: int, status: str) -> None:
    payout = {
        "organizer": "olga",
        "event_id": event_id,
        "amount_cents": amount_cents,
        "bank_account": "0170099220000067797370",
        "status": status,
    }
    insert("payouts", payout)


def load() -> None:
    """Drop everything and start again from the opening data."""
    with LOCK:
        clear()
        add_account("ana", "ana@example.com", "buyer")
        add_account("beto", "beto@example.com", "buyer")
        add_account("olga", "olga@ritmo-producciones.example", "organizer")
        add_account("admin", "admin@boleteria.example", "staff", is_admin=True)
        add_account("carla", "carla@example.com", "buyer")

        add_venue("Teatro del Puerto", "Buenos Aires", 3200)
        add_venue("Estadio Central", "Buenos Aires", 8400)
        add_venue("Sala Rivadavia", "Rosario", 1450)

        add_event("Festival Río Sonoro", "Two nights of live bands by the river.", "music", 2, 6000)
        add_event("Hamlet", "The classic tragedy, staged by Compañía del Sur.", "theatre", 1, 1200)
        add_event("Noche de Stand-up", "Five comedians, one microphone.", "comedy", 3, 900)
        add_event("Unplugged en la Terraza", "An acoustic set for twelve.", "music", 3, 12)

        add_show(1, "2026-12-05 21:00", "2026-12-05 23:30", 4_500_000)
        add_show(1, "2026-12-06 21:00", "2026-12-06 23:30", 4_500_000)
        add_show(2, "2026-11-20 20:30", "2026-11-20 23:00", 2_800_000)
        add_show(2, "2026-11-21 20:30", "2026-11-21 23:00", 2_800_000)
        add_show(3, "2026-11-27 22:00", "2026-11-27 23:45", 1_500_000)
        add_show(4, "2026-12-12 20:00", "2026-12-12 21:30", 2_000_000)

        insert("coupons", {"code": "VERANO10", "percent_off": 10, "active": True})
        insert("coupons", {"code": "AMIGOS20", "percent_off": 20, "active": True})

        add_order(buyer_id=1, show_id=1, seats=2, coupon_code="", paid=True)
        add_order(buyer_id=2, show_id=5, seats=4, coupon_code="VERANO10", paid=False)
        add_order(buyer_id=5, show_id=6, seats=8, coupon_code="", paid=True)
        add_order(buyer_id=5, show_id=6, seats=2, coupon_code="AMIGOS20", paid=True)

        add_payout(event_id=1, amount_cents=8_100_000, status="scheduled")
        add_payout(event_id=2, amount_cents=0, status="pending")
