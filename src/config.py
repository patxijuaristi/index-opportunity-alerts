"""
Configuration module.

All constants, asset definitions, and DCA thresholds live here.
To add a new asset, append a TickerConfig entry to MONITORED_ASSETS.
To adjust signal levels, edit DCA_LEVELS.
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Asset definitions
# ---------------------------------------------------------------------------


@dataclass
class TickerConfig:
    """Configuration for a monitored asset.

    Attributes:
        symbol: Ticker symbol as used by Yahoo Finance (e.g. 'QQQ').
        name: Human-readable name shown in alerts.
        periods: Trading-day lookback windows for drawdown calculation.
    """

    symbol: str
    name: str
    periods: list[int] = field(default_factory=lambda: [5, 30, 60, 90, 180])


# Add new assets here — no other file needs to change.
MONITORED_ASSETS: list[TickerConfig] = [
    TickerConfig(symbol="QQQ", name="Nasdaq-100 ETF (QQQ)"),
]


# ---------------------------------------------------------------------------
# Data-fetch settings
# ---------------------------------------------------------------------------

# Calendar days passed to yfinance. Must comfortably exceed the longest
# trading-day period (180 td ≈ 252 cd) plus a safety buffer.
HISTORICAL_DAYS: int = 300

# Minimum number of trading days required after the fetch.
# Set to the longest period so every drawdown window is fully covered.
MIN_TRADING_DAYS: int = 180


# ---------------------------------------------------------------------------
# DCA signal levels
# ---------------------------------------------------------------------------

# Ordered list of (upper_bound, level_index) thresholds.
# A drawdown value sits in level N when it is <= thresholds[N-1] but
# > thresholds[N].  Level 0 means the market is healthy (drawdown > -5 %).
DCA_LEVEL_THRESHOLDS: list[float] = [-5.0, -10.0, -15.0, -20.0, -30.0]

# Full metadata for each level (index = level number).
DCA_LEVELS: dict[int, dict] = {
    0: {
        "label": "HEALTHY",
        "emoji": "✅",
        "multiplier": 0.0,
        "description": "Market is healthy. Maintain your regular DCA schedule.",
    },
    1: {
        "label": "MILD DIP",
        "emoji": "🟡",
        "multiplier": 1.5,
        "description": "Light pullback detected. Consider investing 1.5× your regular DCA amount.",
    },
    2: {
        "label": "MODERATE DIP",
        "emoji": "🟠",
        "multiplier": 2.0,
        "description": "Moderate correction. Consider investing 2× your regular DCA amount.",
    },
    3: {
        "label": "MAJOR DIP",
        "emoji": "🔴",
        "multiplier": 3.0,
        "description": "Significant drawdown. Consider investing 3× your regular DCA amount.",
    },
    4: {
        "label": "SEVERE DIP",
        "emoji": "🆘",
        "multiplier": 4.0,
        "description": "Severe drawdown. Consider investing 4× your regular DCA amount.",
    },
    5: {
        "label": "CRASH",
        "emoji": "💥",
        "multiplier": 5.0,
        "description": "Market crash territory. Consider investing 5× your regular DCA amount.",
    },
}


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

STATE_DIR: str = "state"
STATE_FILE: str = "state/state.json"


# ---------------------------------------------------------------------------
# Flash crash detection
# ---------------------------------------------------------------------------

# A single-day close-to-close drop equal to or worse than this value triggers
# an immediate alert, independently of the DCA level state machine.
FLASH_CRASH_DAILY_THRESHOLD: float = -5.0
