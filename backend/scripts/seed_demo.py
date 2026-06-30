"""Seed a couple of polished, camera-ready example tasks.

    python -m scripts.seed_demo [base_url]

Reads OPERATOR_TOKEN from backend/.env.
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv(".env")
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
H = {"Authorization": f"Bearer {os.environ.get('OPERATOR_TOKEN', '')}"}

TASKS = [
    {
        "name": "Senior Python Service",
        "rubric": {
            "criteria": [
                {"key": "has_readme", "title": "Has documentation", "type": "gate",
                 "gate_policy": "must_pass",
                 "instructions": "The repository includes a `README` describing setup and usage."},
                {"key": "has_tests", "title": "Automated tests", "type": "scored", "weight": 40,
                 "instructions": "Includes automated `test` functions (pytest/unittest, `def test_`)."},
                {"key": "error_handling", "title": "Error handling", "type": "scored", "weight": 30,
                 "instructions": "Uses explicit `try`/`except` handling rather than silent failures."},
                {"key": "type_hints", "title": "Type hints", "type": "scored", "weight": 30,
                 "instructions": "Uses Python type hints, e.g. `def f(x: int) -> str`."},
            ],
            "decision_config": {"accept_at": 70, "review_at": 45},
        },
    },
    {
        "name": "Next.js Frontend",
        "rubric": {
            "criteria": [
                {"key": "app_router", "title": "App Router", "type": "gate",
                 "gate_policy": "must_pass",
                 "instructions": "Uses the Next.js `app` router (an app/ directory with `page` files)."},
                {"key": "typescript", "title": "TypeScript", "type": "scored", "weight": 40,
                 "instructions": "Written in `typescript` with typed components."},
                {"key": "components", "title": "Componentized", "type": "scored", "weight": 30,
                 "instructions": "UI split into reusable `components`."},
                {"key": "styling", "title": "Consistent styling", "type": "scored", "weight": 30,
                 "instructions": "Uses a consistent styling approach (`tailwind` or `css`)."},
            ],
            "decision_config": {"accept_at": 70, "review_at": 45},
        },
    },
]


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE, timeout=30, headers=H) as c:
        for t in TASKS:
            task = (await c.post("/api/tasks", json={"name": t["name"]})).json()
            tid = task["id"]
            await c.put(f"/api/tasks/{tid}/rubric", json=t["rubric"])
            r = (await c.post(f"/api/tasks/{tid}/rubric/publish")).json()
            print(f"seeded {t['name']} -> v{r['version_number']}")


if __name__ == "__main__":
    asyncio.run(main())
