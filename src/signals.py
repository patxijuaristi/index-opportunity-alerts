"""
DCA signal module.

Maps a drawdown percentage to an actionable DCA level and decides
whether an alert should be dispatched.  All functions are pure.
"""

import logging
from typing import Any, Optional

from src.config import DCA_LEVEL_THRESHOLDS, DCA_LEVELS, FLASH_CRASH_DAILY_THRESHOLD, VIX_BANDS

logger = logging.getLogger(__name__)


def get_dca_level(drawdown: float) -> int:
    """Determine the DCA signal level for a given drawdown percentage.

    Level assignment (thresholds configurable in ``src/config.py``):

    +---------+--------------------+
    | Level 0 | drawdown > -5 %    |
    | Level 1 | -10 % < dd ≤ -5 %  |
    | Level 2 | -15 % < dd ≤ -10 % |
    | Level 3 | -20 % < dd ≤ -15 % |
    | Level 4 | -30 % < dd ≤ -20 % |
    | Level 5 | dd ≤ -30 %         |
    +---------+--------------------+

    Args:
        drawdown: Reference drawdown percentage (negative or zero).

    Returns:
        Integer level from 0 (healthy) to ``len(DCA_LEVEL_THRESHOLDS)``
        (worst crash).
    """
    for level, threshold in enumerate(DCA_LEVEL_THRESHOLDS):
        if drawdown > threshold:
            logger.debug("Drawdown %.2f%% → level %d", drawdown, level)
            return level

    max_level: int = len(DCA_LEVEL_THRESHOLDS)
    logger.debug("Drawdown %.2f%% → level %d (max)", drawdown, max_level)
    return max_level


def get_level_info(level: int) -> dict[str, Any]:
    """Return the full metadata dict for a DCA level.

    Args:
        level: Integer level (0–5).

    Returns:
        Dict with keys ``label``, ``emoji``, ``multiplier``, and
        ``description``.  Falls back to level 0 for unknown values.
    """
    return DCA_LEVELS.get(level, DCA_LEVELS[0])


def should_send_alert(current_level: int, last_level: Optional[int]) -> bool:
    """Decide whether a Telegram alert should be sent.

    Rules:
    - First run (``last_level`` is ``None``): alert only if not healthy (> 0).
    - Subsequent runs: alert only when the level has changed.
    - Recovering *to* level 0 from a higher level triggers an alert so the
      user knows the drawdown has resolved.
    - Staying at level 0 never triggers an alert.

    Args:
        current_level: DCA level computed from today's data.
        last_level: Level stored in the persisted state file, or ``None``
            if no state exists yet.

    Returns:
        ``True`` if an alert should be sent, ``False`` otherwise.
    """
    if last_level is None:
        # First run: only alert when there is something actionable
        result: bool = current_level > 0
        logger.info(
            "First run — current level: %d → send alert: %s",
            current_level,
            result,
        )
        return result

    result = current_level != last_level
    logger.info(
        "Level change check: %s → %d → send alert: %s",
        last_level,
        current_level,
        result,
    )
    return result


def is_flash_crash(daily_change: float) -> bool:
    """Return True when a single-day drop meets or exceeds the flash crash threshold.

    This check is completely independent of the DCA level state machine —
    it fires on the raw daily close-to-close move.

    Args:
        daily_change: Close-to-close percentage change for today (negative = down).

    Returns:
        ``True`` if ``daily_change`` is at or below
        ``FLASH_CRASH_DAILY_THRESHOLD`` (default −5 %).
    """
    result: bool = daily_change <= FLASH_CRASH_DAILY_THRESHOLD
    logger.info(
        "Flash crash check: %.2f%% (threshold %.2f%%) → %s",
        daily_change,
        FLASH_CRASH_DAILY_THRESHOLD,
        result,
    )
    return result


def get_vix_sentiment(vix_value: float) -> dict:
    """Return the sentiment band metadata for a given VIX reading.

    Bands are defined in ``VIX_BANDS`` in ``src/config.py`` and are ordered
    from lowest (Extreme Greed) to highest (Extreme Fear).  The function
    walks the list and returns the last band whose ``min`` threshold the
    VIX value meets or exceeds.

    Args:
        vix_value: Latest VIX closing value (e.g. ``22.5``).

    Returns:
        Dict with keys ``min``, ``label``, ``emoji``, and ``description``
        for the matching band.
    """
    band: dict = VIX_BANDS[0]
    for b in VIX_BANDS:
        if vix_value >= b["min"]:
            band = b

    logger.info(
        "VIX %.2f → sentiment: %s %s",
        vix_value,
        band["emoji"],
        band["label"],
    )
    return band
