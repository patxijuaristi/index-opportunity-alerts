"""
Telegram notifier module.

Sends formatted HTML alert messages via the Telegram Bot API.
Failures are logged and return False — they never raise (non-fatal).
The only exception is a missing environment variable, which raises
EnvironmentError so the caller can decide whether to abort.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_REQUEST_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_credentials() -> tuple[str, str]:
    """Read Telegram credentials from environment variables.

    Returns:
        Tuple of ``(bot_token, chat_id)``.

    Raises:
        EnvironmentError: If either variable is missing or empty.
    """
    token: Optional[str] = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id: Optional[str] = os.environ.get("TELEGRAM_CHAT_ID")

    if not token:
        raise EnvironmentError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Add it to your GitHub repository secrets."
        )
    if not chat_id:
        raise EnvironmentError(
            "TELEGRAM_CHAT_ID environment variable is not set. "
            "Add it to your GitHub repository secrets."
        )

    return token, chat_id


def _format_message(
    symbol: str,
    name: str,
    current_price: float,
    drawdowns: dict[int, float],
    reference_drawdown: float,
    current_level: int,
    last_level: Optional[int],
    level_info: dict[str, Any],
    vix_value: Optional[float],
    vix_info: Optional[dict],
) -> str:
    """Build the HTML-formatted Telegram message body.

    Args:
        symbol: Ticker symbol (e.g. ``'QQQ'``).
        name: Human-readable asset name.
        current_price: Latest closing price in USD.
        drawdowns: Mapping of ``{period: drawdown_percent}``.
        reference_drawdown: Worst drawdown used as the signal input.
        current_level: New DCA signal level.
        last_level: Previous DCA level (``None`` on first run).
        level_info: Metadata dict for ``current_level`` from config.
        vix_value: Latest VIX reading, or ``None`` if unavailable.
        vix_info: VIX sentiment band metadata, or ``None`` if unavailable.

    Returns:
        UTF-8 HTML string ready for Telegram's ``parse_mode=HTML``.
    """
    # Direction indicator
    if last_level is None:
        direction = "🆕 First signal detected"
    elif current_level > last_level:
        direction = f"📉 Drawdown deepening  ({last_level} → {current_level})"
    elif current_level < last_level:
        direction = f"📈 Market recovering  ({last_level} → {current_level})"
    else:
        direction = f"➡️ Level unchanged  ({current_level})"

    # Per-period drawdown breakdown
    drawdown_lines: str = "\n".join(
        f"  • <b>{period}d:</b>  {dd:+.2f}%"
        for period, dd in sorted(drawdowns.items())
    )

    # VIX sentiment block
    if vix_value is not None and vix_info is not None:
        vix_block = (
            f"📊 <b>Market Sentiment (VIX):</b> {vix_value:.1f}  "
            f"{vix_info['emoji']} <b>{vix_info['label']}</b>\n"
            f"  {vix_info['description']}\n\n"
        )
    else:
        vix_block = ""

    # Action block
    if current_level == 0:
        action_block = (
            "📊 Market is healthy.\n"
            "Continue your <b>regular DCA schedule</b>."
        )
    else:
        action_block = (
            f"💡 <b>DCA Signal:</b> {level_info['description']}\n"
            f"   Multiplier: <b>{level_info['multiplier']}×</b> regular DCA"
        )

    timestamp: str = (
        datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )

    message = (
        f"{level_info['emoji']} <b>DCA Index Opportunity Alert</b>\n\n"
        f"<b>Asset:</b> {name}  (<code>{symbol}</code>)\n"
        f"<b>Price:</b> ${current_price:,.2f}\n"
        f"<b>Signal level:</b> {current_level} — {level_info['label']}\n"
        f"<b>Status:</b> {direction}\n\n"
        f"📉 <b>Drawdown breakdown:</b>\n"
        f"{drawdown_lines}\n"
        f"  ↳ <b>Reference (worst):</b>  {reference_drawdown:+.2f}%\n\n"
        f"{vix_block}"
        f"{action_block}\n\n"
        f"<i>🕐 {timestamp}</i>"
    )

    return message


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def send_alert(
    symbol: str,
    name: str,
    current_price: float,
    drawdowns: dict[int, float],
    reference_drawdown: float,
    current_level: int,
    last_level: Optional[int],
    level_info: dict[str, Any],
    vix_value: Optional[float] = None,
    vix_info: Optional[dict] = None,
) -> bool:
    """Send a DCA signal alert via Telegram.

    Args:
        symbol: Ticker symbol.
        name: Human-readable asset name.
        current_price: Latest close price.
        drawdowns: Per-period drawdown results.
        reference_drawdown: Worst drawdown (signal input).
        current_level: New DCA level.
        last_level: Previous DCA level (``None`` on first run).
        level_info: Level metadata from config.
        vix_value: Latest VIX reading, or ``None`` if unavailable.
        vix_info: VIX sentiment band metadata, or ``None`` if unavailable.

    Returns:
        ``True`` if the message was accepted by the Telegram API, ``False``
        on any network or API error.

    Raises:
        EnvironmentError: If required environment variables are absent.
    """
    try:
        token, chat_id = _get_credentials()
    except EnvironmentError:
        raise  # Fatal — let main.py handle it

    message: str = _format_message(
        symbol=symbol,
        name=name,
        current_price=current_price,
        drawdowns=drawdowns,
        reference_drawdown=reference_drawdown,
        current_level=current_level,
        last_level=last_level,
        level_info=level_info,
        vix_value=vix_value,
        vix_info=vix_info,
    )

    url: str = _TELEGRAM_API_URL.format(token=token)
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(
            url, json=payload, timeout=_REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()

        result: dict[str, Any] = response.json()
        if result.get("ok"):
            logger.info("Telegram alert sent successfully for %s.", symbol)
            return True

        logger.error(
            "Telegram API rejected the request for %s: %s", symbol, result
        )
        return False

    except requests.exceptions.Timeout:
        logger.error(
            "Telegram API request timed out after %ds for %s.",
            _REQUEST_TIMEOUT_SECONDS,
            symbol,
        )
        return False
    except requests.exceptions.HTTPError as exc:
        logger.error(
            "Telegram API HTTP error for %s: %s", symbol, exc
        )
        return False
    except requests.exceptions.RequestException as exc:
        logger.error(
            "Telegram API network error for %s: %s", symbol, exc
        )
        return False


def send_flash_crash_alert(
    symbol: str,
    name: str,
    current_price: float,
    daily_change: float,
    vix_value: Optional[float] = None,
    vix_info: Optional[dict] = None,
) -> bool:
    """Send an urgent flash-crash alert via Telegram.

    This alert fires on a single large daily drop and is entirely independent
    of the DCA level state machine — no state is read or written.

    Args:
        symbol: Ticker symbol.
        name: Human-readable asset name.
        current_price: Latest close price.
        daily_change: Close-to-close percentage change that triggered the alert.
        vix_value: Latest VIX reading, or ``None`` if unavailable.
        vix_info: VIX sentiment band metadata, or ``None`` if unavailable.

    Returns:
        ``True`` if the message was delivered, ``False`` on any error.

    Raises:
        EnvironmentError: If required environment variables are absent.
    """
    try:
        token, chat_id = _get_credentials()
    except EnvironmentError:
        raise

    timestamp: str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if vix_value is not None and vix_info is not None:
        vix_block = (
            f"📊 <b>VIX:</b> {vix_value:.1f}  "
            f"{vix_info['emoji']} <b>{vix_info['label']}</b>\n"
            f"  {vix_info['description']}\n\n"
        )
    else:
        vix_block = ""

    message: str = (
        f"⚡ <b>FLASH CRASH ALERT</b>\n\n"
        f"<b>Asset:</b> {name}  (<code>{symbol}</code>)\n"
        f"<b>Price:</b> ${current_price:,.2f}\n"
        f"<b>Daily drop:</b> <b>{daily_change:+.2f}%</b>\n\n"
        f"{vix_block}"
        f"⚠️ Single-day close-to-close drop exceeded the −5 % flash crash threshold.\n"
        f"This alert fires independently of the regular DCA signal level.\n\n"
        f"💡 Consider deploying a portion of your cash reserve immediately "
        f"without waiting for the next scheduled DCA date.\n\n"
        f"<i>🕐 {timestamp}</i>"
    )

    url: str = _TELEGRAM_API_URL.format(token=token)
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(
            url, json=payload, timeout=_REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()

        result: dict[str, Any] = response.json()
        if result.get("ok"):
            logger.info("Flash crash alert sent successfully for %s.", symbol)
            return True

        logger.error(
            "Telegram API rejected flash crash alert for %s: %s", symbol, result
        )
        return False

    except requests.exceptions.RequestException as exc:
        logger.error("Telegram flash crash alert failed for %s: %s", symbol, exc)
        return False
