"""make_openapi.py: writes openapi.json from the running code."""

from __future__ import annotations

import json
from pathlib import Path

from boleteria.app import app

HERE = Path(__file__).resolve().parent


def main() -> None:
    spec = app.openapi()
    (HERE / "openapi.json").write_text(
        json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    operations = sum(len(item) for item in spec["paths"].values())
    print(f"openapi.json: {len(spec['paths'])} paths, {operations} operations")


if __name__ == "__main__":
    main()
