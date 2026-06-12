"""
State manager module.

Persists and retrieves per-asset DCA state in a single JSON file
(``state/state.json``).  The file is keyed by ticker symbol so multiple
assets coexist safely.

Read failures fall back to defaults and never crash the application.
Write failures raise RuntimeError because lost state would cause duplicate
or missed alerts on the next run.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.config import STATE_DIR, STATE_FILE

logger = logging.getLogger(__name__)

# Shape of a single asset's state record
_DEFAULT_STATE: dict[str, Any] = {
    "last_level": None,
    "last_drawdown": None,
    "last_updated": None,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_state_dir() -> None:
    """Create the state directory if it does not exist."""
    Path(STATE_DIR).mkdir(parents=True, exist_ok=True)


def _read_all_states() -> dict[str, Any]:
    """Read the full state file and return its contents.

    Returns an empty dict if the file is missing or unreadable.
    """
    state_path = Path(STATE_FILE)

    if not state_path.exists():
        logger.info("State file not found at '%s'. Starting fresh.", STATE_FILE)
        return {}

    try:
        with state_path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Could not read state file '%s': %s. Falling back to defaults.",
            STATE_FILE,
            exc,
        )
        return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_state(symbol: str) -> dict[str, Any]:
    """Load persisted state for a given ticker symbol.

    Args:
        symbol: Ticker symbol (e.g. ``'QQQ'``).

    Returns:
        Dict with keys ``last_level`` (int | None), ``last_drawdown``
        (float | None), and ``last_updated`` (ISO-8601 str | None).
        Returns defaults when the file is missing or the symbol has no entry.
    """
    _ensure_state_dir()
    all_states: dict[str, Any] = _read_all_states()
    state: dict[str, Any] = all_states.get(symbol, dict(_DEFAULT_STATE))

    logger.info(
        "Loaded state for %s — last_level=%s, last_drawdown=%s, last_updated=%s",
        symbol,
        state.get("last_level"),
        state.get("last_drawdown"),
        state.get("last_updated"),
    )

    return state


def save_state(symbol: str, level: int, drawdown: float) -> None:
    """Persist the current DCA state for a ticker symbol.

    Merges with existing entries so other symbols are not overwritten.

    Args:
        symbol: Ticker symbol.
        level: Current DCA signal level.
        drawdown: Reference drawdown percentage that produced this level.

    Raises:
        RuntimeError: If the state file cannot be written.
    """
    _ensure_state_dir()

    all_states: dict[str, Any] = _read_all_states()

    all_states[symbol] = {
        "last_level": level,
        "last_drawdown": round(drawdown, 2),
        "last_updated": datetime.now(tz=timezone.utc).isoformat(),
    }

    try:
        with Path(STATE_FILE).open("w", encoding="utf-8") as fh:
            json.dump(all_states, fh, indent=2)
            fh.write("\n")  # POSIX-friendly trailing newline
    except OSError as exc:
        raise RuntimeError(
            f"Failed to write state file '{STATE_FILE}': {exc}"
        ) from exc

    logger.info(
        "Saved state for %s — level=%d, drawdown=%.2f%%",
        symbol,
        level,
        drawdown,
    )


def get_last_level(symbol: str) -> Optional[int]:
    """Convenience wrapper: return only the last saved level.

    Args:
        symbol: Ticker symbol.

    Returns:
        Previously saved integer level, or ``None`` if no state exists.
    """
    return load_state(symbol).get("last_level")
