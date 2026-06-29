"""
Drawdown calculation module.

All functions are pure (no I/O), making them straightforward to unit-test.

Drawdown formula
----------------
    drawdown = ((current_price − max_N) / max_N) × 100

where ``max_N`` is the highest closing price over the last N trading days
and ``current_price`` is the most recent closing price.
"""

import logging
import math

import pandas as pd

logger = logging.getLogger(__name__)


def calculate_drawdown(df: pd.DataFrame, period: int) -> float:
    """Calculate the drawdown percentage for a single lookback period.

    Args:
        df: DataFrame with at least a ``'Close'`` column, sorted
            oldest-to-newest.
        period: Number of trading days to look back (e.g. 30, 60, 90, 180).

    Returns:
        Drawdown as a percentage (≤ 0). A value of ``-8.5`` means the asset
        is 8.5 % below its peak for that window.

    Raises:
        ValueError: If ``df`` contains fewer rows than ``period``.
    """
    if len(df) < period:
        raise ValueError(
            f"Insufficient data: {len(df)} trading days available, "
            f"{period} required for this window."
        )

    window: pd.Series = df["Close"].iloc[-period:]
    max_price: float = float(window.max())
    current_price: float = float(df["Close"].iloc[-1])

    if math.isnan(max_price) or math.isnan(current_price) or max_price == 0:
        raise ValueError(
            f"Invalid price data for {period}-day window: "
            f"max={max_price}, current={current_price}"
        )

    drawdown: float = round(((current_price - max_price) / max_price) * 100, 2)

    logger.debug(
        "%d-day window: max=$%.2f, current=$%.2f → drawdown=%.2f%%",
        period,
        max_price,
        current_price,
        drawdown,
    )

    return drawdown


def calculate_all_drawdowns(
    df: pd.DataFrame, periods: list[int]
) -> dict[int, float]:
    """Calculate drawdowns for every requested period.

    Periods for which there is insufficient data are skipped with a warning
    rather than raising, so a partial result is still usable.

    Args:
        df: DataFrame with at least a ``'Close'`` column.
        periods: List of trading-day lookback windows.

    Returns:
        Mapping of ``{period: drawdown_percent}`` for successfully calculated
        windows. May be empty if *all* periods fail.
    """
    drawdowns: dict[int, float] = {}

    for period in sorted(periods):
        try:
            drawdowns[period] = calculate_drawdown(df, period)
        except ValueError as exc:
            logger.warning("Skipping %d-day drawdown: %s", period, exc)

    if drawdowns:
        logger.info(
            "Drawdowns calculated: %s",
            {k: f"{v:.2f}%" for k, v in drawdowns.items()},
        )

    return drawdowns


def get_reference_drawdown(drawdowns: dict[int, float]) -> float:
    """Return the worst (most negative) drawdown across all periods.

    Using the worst drawdown as the signal reference ensures the alert
    reflects the most relevant stress window, not just the most recent one.

    Args:
        drawdowns: Mapping of ``{period: drawdown_percent}`` from
            :func:`calculate_all_drawdowns`.

    Returns:
        The minimum (most negative) drawdown value.

    Raises:
        ValueError: If ``drawdowns`` is empty.
    """
    if not drawdowns:
        raise ValueError(
            "Cannot determine reference drawdown: no drawdown values provided."
        )

    reference: float = min(drawdowns.values())
    worst_period: int = min(drawdowns, key=drawdowns.get)  # type: ignore[arg-type]

    logger.info(
        "Reference drawdown: %.2f%% (from %d-day window)",
        reference,
        worst_period,
    )

    return reference


def calculate_daily_change(df: pd.DataFrame) -> float:
    """Calculate the close-to-close percentage change for the latest trading day.

    Args:
        df: DataFrame with at least a ``'Close'`` column, sorted
            oldest-to-newest, containing at least 2 rows.

    Returns:
        Percentage change (positive = up, negative = down). A value of
        ``-6.1`` means the asset closed 6.1 % lower than the previous day.

    Raises:
        ValueError: If ``df`` has fewer than 2 rows.
    """
    if len(df) < 2:
        raise ValueError(
            f"Cannot calculate daily change: need at least 2 rows, got {len(df)}."
        )

    previous_close: float = float(df["Close"].iloc[-2])
    current_close: float = float(df["Close"].iloc[-1])

    change: float = round(
        ((current_close - previous_close) / previous_close) * 100, 2
    )

    logger.debug(
        "Daily change: prev=$%.2f, current=$%.2f → %.2f%%",
        previous_close,
        current_close,
        change,
    )

    return change
