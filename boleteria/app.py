"""Boletería: a ticketing API. Run it with `python -m uvicorn boleteria.app:app --port 8600`."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import seed
from .routers import admin, buyers, coupons, events, login, orders, shows, venues

REQUEST_LOG = Path(__file__).resolve().parent.parent / "requests.jsonl"

app = FastAPI(
    title="Boletería",
    version="1.0",
    description="Tickets for live events: organizers publish shows, buyers reserve and pay.",
    servers=[{"url": "http://127.0.0.1:8600"}],
    redirect_slashes=False,
)


class Health(BaseModel):
    ok: bool


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        line = {
            "t": round(time.time(), 3),
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "auth": request.headers.get("authorization", ""),
        }
        with REQUEST_LOG.open("a", encoding="utf-8") as log:
            log.write(json.dumps(line) + "\n")


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
    """Each validation error as the three fields the validation answer declares."""
    detail = [
        {"loc": list(found["loc"]), "msg": found["msg"], "type": found["type"]}
        for found in error.errors()
    ]
    return JSONResponse({"detail": detail}, status_code=422)


@app.get("/health", operation_id="health", response_model=Health, tags=["status"])
def health() -> Health:
    return Health(ok=True)


@app.post("/_reset", include_in_schema=False, response_model=Health)
def reset() -> Health:
    """Back to the opening data."""
    seed.load()
    return Health(ok=True)


for module in (login, buyers, venues, events, shows, orders, coupons, admin):
    app.include_router(module.router)

seed.load()
