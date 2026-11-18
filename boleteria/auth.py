"""Who is calling: signed bearer tokens, the session dependencies and the role guard."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .kernel import table

bearer = HTTPBearer(auto_error=False)
_SIGNING_KEY = secrets.token_bytes(32)


@dataclass(frozen=True)
class User:
    id: int
    name: str
    role: str


def password_hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def role_of(account: dict[str, Any]) -> str:
    return "admin" if account["is_admin"] else account["role"]


def _encoded(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decoded(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(payload: str) -> str:
    return _encoded(hmac.new(_SIGNING_KEY, payload.encode(), hashlib.sha256).digest())


def issue_token(account: dict[str, Any]) -> str:
    """A token naming the account and its role, signed, good for twelve hours."""
    lifetime_s = 12 * 60 * 60
    claims = {"sub": account["id"], "role": role_of(account), "exp": int(time.time()) + lifetime_s}
    payload = _encoded(json.dumps(claims, separators=(",", ":")).encode())
    return f"{payload}.{_signature(payload)}"


def claims_of(token: str) -> dict[str, Any] | None:
    """What a token claims, or nothing when its signature or its shape is wrong."""
    payload, _, signature = token.partition(".")
    if not hmac.compare_digest(signature.encode(), _signature(payload).encode()):
        return None
    try:
        claims = json.loads(_decoded(payload))
    except ValueError:
        return None
    return claims if isinstance(claims, dict) else None


def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User | None:
    """The account behind a token that is signed, not expired and still on record."""
    claims = claims_of(credentials.credentials) if credentials else None
    if claims is None or claims.get("exp", 0) <= time.time():
        return None
    account = table("accounts").get(claims.get("sub", 0))
    if account is None or role_of(account) != claims.get("role"):
        return None
    return User(id=account["id"], name=account["name"], role=role_of(account))


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


def require_role(role: str) -> Callable[[User], User]:
    def guard(user: User = Depends(current_user)) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail=f"{role} only")
        return user

    return guard
