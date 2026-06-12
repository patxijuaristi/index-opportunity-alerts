#!/usr/bin/env python3
"""
Telegram connectivity test.

Sends a real formatted test message to verify that:
  - TELEGRAM_BOT_TOKEN is valid
  - TELEGRAM_CHAT_ID is reachable
  - The bot can post HTML messages

Usage (run from the project root):
    python tests/test_telegram.py

Reads credentials from environment variables.  If a .env file is present
in the project root, load it first:

    export $(grep -v '^#' .env | xargs) && python tests/test_telegram.py

Or install python-dotenv and it will be loaded automatically.
"""

import logging
import os
import sys
from datetime import datetime, timezone

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auto-load .env if python-dotenv is available
# .env lives in the project root (one level above this file)
# ---------------------------------------------------------------------------
try:
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
    logger.info("Loaded credentials from .env file.")
except ImportError:
    pass  # No dotenv installed — rely on environment variables already set


def main() -> int:
    token: str | None = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id: str | None = os.environ.get("TELEGRAM_CHAT_ID")

    if not token:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set.\n"
            "  Option A: export TELEGRAM_BOT_TOKEN=<your_token>\n"
            "  Option B: add it to a .env file in the project root"
        )
        return 1
    if not chat_id:
        logger.error(
            "TELEGRAM_CHAT_ID is not set.\n"
            "  Option A: export TELEGRAM_CHAT_ID=<your_chat_id>\n"
            "  Option B: add it to a .env file in the project root"
        )
        return 1

    # Mask token in logs for safety
    masked_token = token[:10] + "..." + token[-4:]
    logger.info("Token   : %s", masked_token)
    logger.info("Chat ID : %s", chat_id)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    message = (
        "🤖 <b>Index Opportunity Alerts — Connectivity Test</b>\n\n"
        "✅ Your Telegram bot is configured correctly!\n\n"
        "<b>Checklist:</b>\n"
        "  ✔ Bot token is valid\n"
        "  ✔ Chat ID is reachable\n"
        "  ✔ HTML formatting works\n\n"
        "You will receive DCA alerts in this chat when QQQ\n"
        "drops below the configured drawdown thresholds.\n\n"
        f"<i>🕐 {timestamp}</i>"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    logger.info("Sending test message to Telegram...")
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()
    except requests.exceptions.ConnectionError:
        logger.error("Network error — could not reach api.telegram.org")
        return 1
    except requests.exceptions.Timeout:
        logger.error("Request timed out after 15 seconds")
        return 1
    except requests.exceptions.HTTPError as exc:
        logger.error("HTTP error: %s", exc)
        # Print raw body to help diagnose bad token / chat ID errors
        logger.error("Response body: %s", exc.response.text)
        return 1

    if result.get("ok"):
        logger.info("✅  Message delivered! Message ID: %s", result["result"]["message_id"])
        logger.info("Check your Telegram chat now.")
        return 0

    logger.error("Telegram API returned ok=false: %s", result)
    return 1


if __name__ == "__main__":
    sys.exit(main())
