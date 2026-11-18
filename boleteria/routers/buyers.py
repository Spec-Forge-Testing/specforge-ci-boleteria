"""Buyer accounts: sign-up and the caller's own profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, model_validator

from ..auth import User, current_user, password_hash
from ..kernel import Strict, insert, problems, reject, stored, well_formed

router = APIRouter(tags=["buyers"])


def documented(schema: dict[str, Any]) -> None:
    """The documented fields only, with a sample body."""
    schema.pop("additionalProperties", None)
    sample = {"name": "Dana Ruiz", "email": "dana@example.com", "password": "dana-2026"}
    schema["examples"] = [sample]


class NewBuyer(Strict):
    model_config = ConfigDict(extra="allow", json_schema_extra=documented)

    name: str
    email: str
    password: str

    @model_validator(mode="after")
    def well_formed_settings(self) -> NewBuyer:
        for value in (self.model_extra or {}).values():
            well_formed(value)
        return self


class BuyerView(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_admin: bool


def known_settings(profile: dict[str, Any], given: dict[str, Any]) -> dict[str, Any]:
    """The given values for settings the profile already holds, when they keep their type."""
    return {
        key: value
        for key, value in given.items()
        if key in profile and type(value) is type(profile[key])
    }


@router.post(
    "/buyers",
    operation_id="createBuyer",
    status_code=201,
    response_model=BuyerView,
    responses=problems(400),
)
def create_buyer(body: NewBuyer) -> dict[str, Any]:
    if not body.name.strip():
        reject("name must not be blank")
    if not body.password:
        reject("password must not be empty")
    profile = {"name": body.name, "email": body.email, "role": "buyer", "is_admin": False}
    profile.update(known_settings(profile, body.model_extra or {}))
    return insert("accounts", {**profile, "password_hash": password_hash(body.password)})


@router.get(
    "/buyers/me",
    operation_id="getMyProfile",
    response_model=BuyerView,
    responses=problems(401),
)
def read_my_profile(user: User = Depends(current_user)) -> JSONResponse:
    return JSONResponse(stored("accounts", user.id))
