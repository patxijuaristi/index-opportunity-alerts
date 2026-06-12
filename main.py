#!/usr/bin/env python3
"""
Index Opportunity Alerts — entry point.

Orchestrates the full pipeline for every configured asset:
  1. Fetch historical price data from Yahoo Finance
  2. Detect flash crash (single-day drop ≥ 5 %) and alert immediately
  3. Calculate drawdowns for all configured periods (5d, 30d, 60d, 90d, 180d)
  4. Determine the current DCA signal level
  5. Compare with persisted state and send a Telegram alert if level changed
  6. Persist the updated state

This module contains **no business logic** — it only wires together the
modules in ``src/``.
"""

import logging
import sys
from typing import Optional

from src.config import HISTORICAL_DAYS, MIN_TRADING_DAYS, MONITORED_ASSETS
from src.data_fetcher import fetch_historical_data
from src.drawdown import calculate_all_drawdowns, calculate_daily_change, get_reference_drawdown
from src.signals import get_dca_level, get_level_info, is_flash_crash, should_send_alert
from src.state_manager import load_state, save_state
from src.telegram_notifier import send_alert, send_flash_crash_alert

# ---------------------------------------------------------------------------
# Logging — configured once at the top level for GitHub Actions compatibility
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-asset processing
# ---------------------------------------------------------------------------


def process_asset(symbol: str, name: str, periods: list[int]) -> bool:
    """Run the full monitoring pipeline for a single asset.

    Args:
        symbol: Ticker symbol (e.g. ``'QQQ'``).
        name: Human-readable asset name for log messages and alerts.
        periods: Drawdown lookback windows in trading days.

    Returns:
        ``True`` when the asset was processed successfully (whether or not
        an alert was sent).  ``False`` when a recoverable error prevents
        completion.

    Raises:
        EnvironmentError: Re-raised from the Telegram notifier when required
            environment variables are absent (fatal — stops all processing).
    """
    logger.info("=" * 60)
    logger.info("Processing: %s (%s)", name, symbol)
    logger.info("=" * 60)

    # ------------------------------------------------------------------ #
    # Step 1 — Fetch historical data                                     #
    # ------------------------------------------------------------------ #
    try:
        df = fetch_historical_data(symbol, days=HISTORICAL_DAYS)
    except RuntimeError as exc:
        logger.error("Data fetch failed for %s: %s", symbol, exc)
        return False

    trading_days: int = len(df)
    if trading_days < MIN_TRADING_DAYS:
        logger.error(
            "Insufficient trading days for %s: %d available, %d required.",
            symbol,
            trading_days,
            MIN_TRADING_DAYS,
        )
        return False

    current_price: float = float(df["Close"].iloc[-1])

    # ------------------------------------------------------------------ #
    # Step 2 — Flash crash detection (independent of DCA level state)     #
    # ------------------------------------------------------------------ #
    try:
        daily_change: float = calculate_daily_change(df)
    except ValueError as exc:
        logger.warning("Could not compute daily change for %s: %s", symbol, exc)
        daily_change = 0.0

    if is_flash_crash(daily_change):
        logger.warning(
            "Flash crash detected for %s: %.2f%% single-day drop.",
            symbol,
            daily_change,
        )
        send_flash_crash_alert(
            symbol=symbol,
            name=name,
            current_price=current_price,
            daily_change=daily_change,
        )

    # ------------------------------------------------------------------ #
    # Step 3 — Calculate drawdowns                                         #
    # ------------------------------------------------------------------ #
    drawdowns: dict[int, float] = calculate_all_drawdowns(df, periods)

    if not drawdowns:
        logger.error("No drawdowns could be calculated for %s.", symbol)
        return False

    # ------------------------------------------------------------------ #
    # Step 4 — Determine reference drawdown and DCA level                 #
    # ------------------------------------------------------------------ #
    try:
        reference_drawdown: float = get_reference_drawdown(drawdowns)
    except ValueError as exc:
        logger.error("Cannot determine reference drawdown for %s: %s", symbol, exc)
        return False

    current_level: int = get_dca_level(reference_drawdown)
    level_info: dict = get_level_info(current_level)

    logger.info(
        "Price: $%.2f | Reference drawdown: %.2f%% | Level: %d (%s)",
        current_price,
        reference_drawdown,
        current_level,
        level_info["label"],
    )

    # ------------------------------------------------------------------ #
    # Step 5 — Load previous state and check whether to alert             #
    # ------------------------------------------------------------------ #
    state: dict = load_state(symbol)
    last_level: Optional[int] = state.get("last_level")

    if not should_send_alert(current_level, last_level):
        logger.info(
            "Level unchanged (%d). No alert dispatched for %s.",
            current_level,
            symbol,
        )
        return True

    logger.info(
        "Level changed: %s → %d. Dispatching Telegram alert for %s...",
        last_level,
        current_level,
        symbol,
    )

    # ------------------------------------------------------------------ #
    # Step 6 — Send Telegram DCA level alert                               #
    # ------------------------------------------------------------------ #
    alert_sent: bool = send_alert(
        symbol=symbol,
        name=name,
        current_price=current_price,
        drawdowns=drawdowns,
        reference_drawdown=reference_drawdown,
        current_level=current_level,
        last_level=last_level,
        level_info=level_info,
    )

    if not alert_sent:
        logger.error(
            "Telegram alert failed for %s. State will NOT be updated to "
            "ensure the alert is retried on the next run.",
            symbol,
        )
        return False

    # ------------------------------------------------------------------ #
    # Step 7 — Persist new state (only on successful alert dispatch)       #
    # ------------------------------------------------------------------ #
    try:
        save_state(symbol, current_level, reference_drawdown)
    except RuntimeError as exc:
        logger.error("State persistence failed for %s: %s", symbol, exc)
        return False

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Iterate over all configured assets and return an appropriate exit code.

    Returns:
        ``0`` if every asset was processed successfully, ``1`` if one or more
        assets encountered an error.
    """
    logger.info("Index Opportunity Alerts — run started")

    results: list[tuple[str, bool]] = []

    for asset in MONITORED_ASSETS:
        try:
            success: bool = process_asset(
                symbol=asset.symbol,
                name=asset.name,
                periods=asset.periods,
            )
        except EnvironmentError as exc:
            # Missing secrets: abort immediately so the CI job fails visibly
            logger.critical("Fatal configuration error: %s", exc)
            return 1

        results.append((asset.symbol, success))

    # ------------------------------------------------------------------ #
    # Run summary                                                          #
    # ------------------------------------------------------------------ #
    logger.info("=" * 60)
    logger.info("Run summary:")
    for symbol, success in results:
        status = "✓ OK" if success else "✗ FAILED"
        logger.info("  %s  %s", status, symbol)
    logger.info("=" * 60)

    failed: list[str] = [sym for sym, ok in results if not ok]
    if failed:
        logger.error("The following assets failed: %s", failed)
        return 1

    logger.info("All assets processed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
