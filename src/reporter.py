"""
Weekly report module.

Generates a comprehensive weekly market digest for all monitored assets.
Unlike the daily monitor (main.py), the weekly report always fires on
schedule regardless of state — it is a digest, not a state-gated alert.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from src.drawdown import calculate_all_drawdowns, get_reference_drawdown
from src.signals import get_dca_level, get_level_info

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------


def _calculate_trailing_return(df: pd.DataFrame, period: int) -> Optional[float]:
    """Calculate the simple price return from N trading days ago to today.

    Unlike drawdown (which measures from the *peak* within a window), this
    is the raw price change from a fixed past point — equivalent to what a
    stock chart shows as "1W", "1M", or "3M" return.

    Args:
        df: DataFrame with at least a ``'Close'`` column, oldest-to-newest.
        period: Number of trading days to look back.

    Returns:
        Percentage return (positive = up, negative = down), or ``None`` if
        there is insufficient data.
    """
    if len(df) < period + 1:
        return None

    price_then: float = float(df["Close"].iloc[-(period + 1)])
    price_now: float = float(df["Close"].iloc[-1])
    return round(((price_now - price_then) / price_then) * 100, 2)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_asset_report(
    symbol: str,
    name: str,
    df: pd.DataFrame,
    periods: list[int],
) -> dict[str, Any]:
    """Generate a comprehensive report dict for a single asset.

    Computes trailing returns, peak-relative drawdowns, DCA signal level,
    and approximate 52-week high from the available price history.

    Args:
        symbol: Ticker symbol (e.g. ``'QQQ'``).
        name: Human-readable asset name.
        df: Historical price DataFrame, sorted oldest-to-newest.
        periods: Drawdown lookback windows in trading days.

    Returns:
        Dict with keys: ``symbol``, ``name``, ``current_price``,
        ``trailing_returns``, ``drawdowns``, ``reference_drawdown``,
        ``dca_level``, ``level_info``, ``high_52w``, ``distance_from_high``.
    """
    current_price: float = float(df["Close"].iloc[-1])

    # Simple trailing returns (raw change from N days ago, not from peak)
    trailing_returns: dict[str, Optional[float]] = {
        "1W": _calculate_trailing_return(df, 5),   # ~1 trading week
        "1M": _calculate_trailing_return(df, 21),  # ~1 trading month
        "3M": _calculate_trailing_return(df, 63),  # ~3 trading months
    }

    # Peak-relative drawdowns (configurable periods from config.py)
    drawdowns: dict[int, float] = calculate_all_drawdowns(df, periods)
    try:
        reference_drawdown: float = get_reference_drawdown(drawdowns)
    except ValueError:
        reference_drawdown = 0.0

    dca_level: int = get_dca_level(reference_drawdown)
    level_info: dict[str, Any] = get_level_info(dca_level)

    # Approximate 52-week high (up to 252 trading days if available)
    lookback: int = min(252, len(df))
    high_52w: float = float(df["Close"].iloc[-lookback:].max())
    distance_from_high: float = round(
        ((current_price - high_52w) / high_52w) * 100, 2
    )

    report: dict[str, Any] = {
        "symbol": symbol,
        "name": name,
        "current_price": current_price,
        "trailing_returns": trailing_returns,
        "drawdowns": drawdowns,
        "reference_drawdown": reference_drawdown,
        "dca_level": dca_level,
        "level_info": level_info,
        "high_52w": high_52w,
        "distance_from_high": distance_from_high,
    }

    ret_1w = trailing_returns["1W"]
    logger.info(
        "Report for %s: price=$%.2f | 1W=%s | ref_dd=%.2f%% | level=%d (%s)",
        symbol,
        current_price,
        f"{ret_1w:+.2f}%" if ret_1w is not None else "N/A",
        reference_drawdown,
        dca_level,
        level_info["label"],
    )
    return report


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _fmt_return(value: Optional[float]) -> str:
    """Format a return value with a direction arrow and sign."""
    if value is None:
        return "N/A"
    arrow = "📈" if value >= 0 else "📉"
    return f"{arrow} {value:+.2f}%"


def _format_asset_block(report: dict[str, Any]) -> str:
    """Format a single asset section for the weekly digest."""
    level_info: dict[str, Any] = report["level_info"]
    trailing: dict[str, Optional[float]] = report["trailing_returns"]

    drawdown_lines: str = "\n".join(
        f"  • <b>{period}d:</b>  {dd:+.2f}%"
        for period, dd in sorted(report["drawdowns"].items())
    )

    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{level_info['emoji']} <b>{report['name']}</b>\n\n"
        f"💰 <b>Price:</b> ${report['current_price']:,.2f}\n"
        f"📅 <b>1 week:</b>    {_fmt_return(trailing.get('1W'))}\n"
        f"📅 <b>1 month:</b>   {_fmt_return(trailing.get('1M'))}\n"
        f"📅 <b>3 months:</b>  {_fmt_return(trailing.get('3M'))}\n"
        f"🏔 <b>52wk high:</b> ${report['high_52w']:,.2f}  "
        f"({report['distance_from_high']:+.2f}% from it)\n\n"
        f"📉 <b>Drawdown from recent peaks:</b>\n"
        f"{drawdown_lines}\n"
        f"  ↳ <b>Reference:</b> {report['reference_drawdown']:+.2f}%\n\n"
        f"🎯 <b>DCA Signal:</b> Level {report['dca_level']} — "
        f"{level_info['label']}\n"
        f"   {level_info['description']}"
    )


def format_weekly_report(
    asset_reports: list[dict[str, Any]],
    vix_value: Optional[float],
    vix_info: Optional[dict],
    report_date: str,
) -> str:
    """Assemble the full weekly digest as an HTML Telegram message.

    Args:
        asset_reports: List of dicts from :func:`generate_asset_report`.
        vix_value: Latest VIX reading, or ``None`` if unavailable.
        vix_info: VIX sentiment band metadata, or ``None`` if unavailable.
        report_date: Human-readable date string shown in the header.

    Returns:
        UTF-8 HTML string ready for Telegram's ``parse_mode=HTML``.
    """
    if vix_value is not None and vix_info is not None:
        vix_block = (
            f"📊 <b>Market Sentiment (VIX):</b> {vix_value:.1f}  "
            f"{vix_info['emoji']} <b>{vix_info['label']}</b>\n"
            f"  {vix_info['description']}\n\n"
        )
    else:
        vix_block = ""

    asset_blocks: str = "\n\n".join(
        _format_asset_block(r) for r in asset_reports
    )
    timestamp: str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return (
        f"📋 <b>Weekly Market Digest</b>\n"
        f"<i>Week ending {report_date}</i>\n\n"
        f"{vix_block}"
        f"{asset_blocks}\n\n"
        f"<i>🕐 {timestamp}</i>"
    )
