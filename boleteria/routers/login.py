"""Signing in: an email and a password for a bearer token."""

from __future__ import annotations

import hmac

from fastapi import APIRouter
from pydantic import BaseModel

from ..auth import issue_token, password_hash
from ..kernel import Strict, example, problems, reject, table

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(Strict):
    model_config = example({"email": "ana@example.com", "password": "ana-2026"})

    email: str
    password: str


class Session(BaseModel):
    token: str


@router.post(
    "/login",
    operation_id="login",
    response_model=Session,
    responses=problems(401),
)
def login(body: Credentials) -> Session:
    given = password_hash(body.password)
    for account in list(table("accounts").values()):
        if account["email"] == body.email and hmac.compare_digest(account["password_hash"], given):
            return Session(token=issue_token(account))
    reject("wrong email or password", 401)
    return Session(token="")
