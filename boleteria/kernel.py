"""What every router shares: strict request models, the in-memory store and the usual refusals."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, field_validator

LOCK = threading.RLock()
_TABLES: defaultdict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
_LAST_ID: defaultdict[str, int] = defaultdict(int)


def well_formed(value: Any) -> Any:
    """The value itself, refused when it is text that is not valid Unicode."""
    if isinstance(value, str) and not value.isascii():
        try:
            value.encode()
        except UnicodeEncodeError:
            raise ValueError("text must be valid Unicode") from None
    return value


class Strict(BaseModel):
    """A request body that never coerces: a string is not an integer."""

    model_config = ConfigDict(strict=True)

    @field_validator("*")
    @classmethod
    def well_formed_text(cls, value: Any) -> Any:
        return well_formed(value)


class Problem(BaseModel):
    detail: str


def example(*bodies: dict[str, Any]) -> ConfigDict:
    """The sample bodies a request model shows in the docs."""
    return ConfigDict(json_schema_extra={"examples": list(bodies)})


def problems(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """The refusals an operation documents, each answered as a `Problem`."""
    return {status_code: {"model": Problem} for status_code in status_codes}


def linked(status_code: int, *operations: str) -> dict[int | str, dict[str, Any]]:
    """The answer whose id is the path parameter of the named operations."""
    links = {
        name: {"operationId": name, "parameters": {"id": "$response.body#/id"}}
        for name in operations
    }
    return {status_code: {"links": links}}


def table(name: str) -> dict[int, dict[str, Any]]:
    return _TABLES[name]


def insert(name: str, row: dict[str, Any]) -> dict[str, Any]:
    with LOCK:
        _LAST_ID[name] += 1
        row["id"] = _LAST_ID[name]
        _TABLES[name][row["id"]] = row
    return row


def stored(name: str, row_id: int) -> dict[str, Any]:
    row = _TABLES[name].get(row_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"{name.removesuffix('s')} not found")
    return row


def clear() -> None:
    with LOCK:
        _TABLES.clear()
        _LAST_ID.clear()


def reject(detail: str, status_code: int = 400) -> None:
    raise HTTPException(status_code=status_code, detail=detail)


def forbid(detail: str) -> None:
    raise HTTPException(status_code=403, detail=detail)
