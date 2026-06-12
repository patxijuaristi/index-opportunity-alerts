#!/usr/bin/env python3
"""
Weekly Market Digest — entry point.

Sends a comprehensive weekly summary for all monitored assets via Telegram.
Unlike main.py (which alerts only on DCA level changes), this script always
sends the full digest when triggered — it is a scheduled report, not a
state-gated alert.

This module contains **no business logic** — it wires together the modules
in ``src/``.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Optional

# Auto-load .env if python-dotenv is available (local development only)
try:
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
except ImportError:
    pass

from src.config import HISTORICAL_DAYS, MONITORED_ASSETS
from src.data_fetcher import fetch_historical_data, fetch_vix
from src.reporter import format_weekly_report, generate_asset_report
from src.signals import get_vix_sentiment
from src.telegram_notifier import send_telegram_message

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Generate and send the weekly market digest.

    Returns:
        ``0`` on success, ``1`` on fatal error.
    """
    logger.info("Weekly Market Digest — run started")

    # ------------------------------------------------------------------ #
    # Step 1 — Fetch VIX once (shared across all assets)                  #
    # ------------------------------------------------------------------ #
    vix_value: Optional[float] = None
    vix_info: Optional[dict] = None
    try:
        vix_value = fetch_vix()
        vix_info = get_vix_sentiment(vix_value)
    except RuntimeError as exc:
        logger.warning(
            "VIX fetch failed — digest will be sent without sentiment: %s", exc
        )

    # ------------------------------------------------------------------ #
    # Step 2 — Generate per-asset reports                                  #
    # ------------------------------------------------------------------ #
    asset_reports: list[dict] = []

    for asset in MONITORED_ASSETS:
        logger.info("Generating report for %s...", asset.symbol)
        try:
            df = fetch_historical_data(asset.symbol, days=HISTORICAL_DAYS)
            report = generate_asset_report(
                symbol=asset.symbol,
                name=asset.name,
                df=df,
                periods=asset.periods,
            )
            asset_reports.append(report)
        except RuntimeError as exc:
            logger.error(
                "Failed to generate report for %s: %s — skipping.", asset.symbol, exc
            )

    if not asset_reports:
        logger.error("No asset reports could be generated. Aborting.")
        return 1

    # ------------------------------------------------------------------ #
    # Step 3 — Format and send                                             #
    # ------------------------------------------------------------------ #
    report_date: str = datetime.now(tz=timezone.utc).strftime("%B %d, %Y")
    message: str = format_weekly_report(asset_reports, vix_value, vix_info, report_date)

    logger.info(
        "Sending weekly digest for %d asset(s): %s",
        len(asset_reports),
        [r["symbol"] for r in asset_reports],
    )

    try:
        sent: bool = send_telegram_message(message)
    except EnvironmentError as exc:
        logger.critical("Fatal configuration error: %s", exc)
        return 1

    if not sent:
        logger.error("Failed to send weekly digest.")
        return 1

    logger.info("Weekly digest sent successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
