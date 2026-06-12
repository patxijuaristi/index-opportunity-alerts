"""
Data fetcher module.

Responsible solely for acquiring historical OHLCV data from Yahoo Finance.
Raises RuntimeError on any API/network failure so callers can handle it.
"""

import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_historical_data(symbol: str, days: int = 300) -> pd.DataFrame:
    """Fetch historical daily close data for a ticker from Yahoo Finance.

    The function requests `days` calendar days of history, which translates
    to roughly ``days * 252 / 365`` trading days — enough to satisfy a
    180-trading-day drawdown window with a comfortable buffer.

    Args:
        symbol: Ticker symbol recognised by Yahoo Finance (e.g. ``'QQQ'``).
        days: Number of calendar days to look back from today.

    Returns:
        A :class:`pandas.DataFrame` with a timezone-naive DatetimeIndex and
        at least a ``'Close'`` column, sorted oldest-to-newest.

    Raises:
        RuntimeError: If the Yahoo Finance request fails or returns no data.
    """
    try:
        end_date: datetime = datetime.now()
        start_date: datetime = end_date - timedelta(days=days)

        logger.info(
            "Fetching %s data from %s to %s",
            symbol,
            start_date.date(),
            end_date.date(),
        )

        ticker = yf.Ticker(symbol)
        df: pd.DataFrame = ticker.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            auto_adjust=True,
        )

        if df.empty:
            raise RuntimeError(f"Yahoo Finance returned no data for '{symbol}'")

        # Normalise index: remove timezone so downstream code is tz-naive
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # Sort ascending (yfinance usually does this, but be explicit)
        df = df.sort_index()

        current_price: float = float(df["Close"].iloc[-1])
        logger.info(
            "Fetched %d trading days for %s — latest close: $%.2f",
            len(df),
            symbol,
            current_price,
        )

        return df

    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch market data for '{symbol}': {exc}"
        ) from exc


def fetch_vix() -> float:
    """Fetch the latest closing value of the CBOE Volatility Index (VIX).

    The VIX (ticker ``^VIX``) measures the 30-day implied volatility of the
    S&P 500 derived from options prices.  High values indicate fear/panic;
    low values indicate complacency/greed.

    Returns:
        Latest VIX closing value as a float (e.g. ``18.42``).

    Raises:
        RuntimeError: If the Yahoo Finance request fails or returns no data.
    """
    try:
        ticker = yf.Ticker("^VIX")
        df: pd.DataFrame = ticker.history(period="5d", auto_adjust=True)

        if df.empty:
            raise RuntimeError("Yahoo Finance returned no data for '^VIX'")

        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        vix_value: float = round(float(df["Close"].iloc[-1]), 2)
        logger.info("VIX latest close: %.2f", vix_value)
        return vix_value

    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch VIX data: {exc}") from exc
