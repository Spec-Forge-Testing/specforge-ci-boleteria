#!/usr/bin/env python
"""Sign in the four seeded users of Boletería and write an identities file.

Usage: python make_identities.py [base_url] [out_file]
  base_url  default http://127.0.0.1:8600
  out_file  default ./identities.toml (relative to the current directory)

Stdlib only (urllib): no dependencies, any Python 3.11+. Works the same on Linux,
macOS and Windows. Tokens expire and stop being valid when the API restarts, so
regenerate the file before each session.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8600"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("identities.toml")
SEEDED = (
    ("ana", "buyer", "ana@example.com", "ana-2026"),
    ("beto", "buyer", "beto@example.com", "beto-2026"),
    ("olga", "organizer", "olga@ritmo-producciones.example", "olga-2026"),
    ("admin", "admin", "admin@boleteria.example", "admin-2026"),
)
FORGED_SIGNATURE = "A" * 43


def _post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def token_for(label: str, email: str, password: str) -> str:
    """Sign the user in and return the bearer token."""
    try:
        body = _post("/auth/login", {"email": email, "password": password})
    except urllib.error.HTTPError as exc:
        refusal = f"Login refused for {label} (HTTP {exc.code}). Was the seed changed?"
        raise SystemExit(refusal) from None
    token = body.get("token", "")
    if not token:
        raise SystemExit(f"No token returned for {label}: {body}")
    return token


def forged(token: str) -> str:
    """The same claims under a signature nobody issued."""
    return f"{token.partition('.')[0]}.{FORGED_SIGNATURE}"


def entry(label: str, header: str = "", role: str = "") -> str:
    kind = f'role = "{role}"' if role else 'credential = "invalid"'
    lines = ["[[identities]]", f'label = "{label}"', kind]
    if header:
        lines += ["[identities.headers]", f'Authorization = "Bearer {header}"']
    return "\n".join(lines) + "\n"


def main() -> None:
    try:
        signed_in = [
            (label, role, token_for(label, email, password))
            for label, role, email, password in SEEDED
        ]
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Cannot reach the API at {BASE} ({exc.reason}).\n"
            "Is it up? python -m uvicorn boleteria.app:app --port 8600 starts it."
        ) from None

    entries = [entry(label, token, role) for label, role, token in signed_in]
    entries.append(entry("intruso", forged(signed_in[0][2])))
    entries.append(entry("anonymous"))
    OUT.write_text("\n".join(entries), encoding="utf-8")
    print(f"wrote {OUT.resolve()}")


if __name__ == "__main__":
    main()
