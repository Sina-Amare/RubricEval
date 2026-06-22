"""
Optional Telegram notifier.

If ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` are configured, a short
message with the decision and a deep link to the web report is sent when a
review finishes. Telegram is a *thin client of this API* — it never runs the
engine itself. Disabled by default; failures never affect the worker.
"""

from __future__ import annotations

import httpx

from app.db.models import Review
from app.settings import get_settings
from app.utils.logger import setup_logger

logger = setup_logger("app.notify.telegram")


async def notify_review_complete(review: Review) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return

    decision = review.decision.value.upper() if review.decision else "—"
    score = f"{review.final_score:.0f}%" if review.final_score is not None else "n/a"
    text = (
        f"✅ Review complete\n"
        f"Decision: {decision}  ·  Score: {score}\n"
        f"{settings.web_base_url}/reviews/{review.id}"
    )
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"chat_id": settings.telegram_chat_id, "text": text})
    except Exception as exc:  # noqa: BLE001 - notifications are best-effort
        logger.warning(f"Telegram notification failed: {exc}")
