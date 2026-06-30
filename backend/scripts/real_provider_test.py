"""Real provider connection test against a running server + live model.

    python -m scripts.real_provider_test [base_url]
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


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=40, headers=H) as c:
        body = (
            await c.post(
                "/api/provider-configs/test",
                json={
                    "provider": "openrouter",
                    "model_id": os.environ.get("DEFAULT_MODEL", ""),
                    "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
                },
            )
        ).json()
        print(
            f"provider-test: ok={body['ok']} latency={body['latency_ms']}ms "
            f"model={body.get('model_id')} msg={body['message']}"
        )
        # And a deliberately bad key should fail with a friendly message.
        bad = (
            await c.post(
                "/api/provider-configs/test",
                json={"provider": "openrouter", "model_id": os.environ.get("DEFAULT_MODEL", ""),
                      "api_key": "sk-or-v1-definitely-invalid-key"},
            )
        ).json()
        print(f"bad-key-test:  ok={bad['ok']} msg={bad['message']}")
        return 0 if (body["ok"] and not bad["ok"]) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
