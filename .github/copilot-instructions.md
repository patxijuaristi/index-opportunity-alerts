# GitHub Copilot Instructions

## Project Overview

This project monitors stock market indexes and ETFs, then generates dynamic DCA (Dollar-Cost Averaging) investment signals based on drawdown analysis. It runs daily via GitHub Actions and delivers alerts through Telegram.

The primary asset is **QQQ** (Nasdaq-100 ETF), but the architecture is designed to scale to multiple indexes or individual equities by simply extending the `MONITORED_ASSETS` list in `src/config.py`.

---

## Architecture

```
main.py               ← Orchestration only, no business logic
src/
  config.py           ← All constants, thresholds, and asset definitions
  data_fetcher.py     ← Data acquisition via yfinance
  drawdown.py         ← Drawdown calculation logic
  signals.py          ← DCA signal level determination
  telegram_notifier.py← Telegram API integration
  state_manager.py    ← JSON-based state persistence
state/
  state.json          ← Persisted per-asset state (committed to repo)
.github/
  workflows/
    monitor.yml       ← Daily GitHub Actions runner
```

---

## Python Standards

- **Python 3.11+** — use modern syntax, including `list[int]` and `dict[str, Any]` annotations
- **Full type hints** on every function signature and variable where the type is non-obvious
- **Dataclasses** for configuration objects (e.g., `TickerConfig`)
- **PEP 8** formatting throughout
- Every public function must have a **docstring** with Args/Returns/Raises sections

---

## Error Handling Rules

| Situation | Behavior |
|---|---|
| Yahoo Finance API failure | Raise `RuntimeError`, let `main.py` log and continue to next asset |
| Telegram API failure | Log error, return `False`, do not raise (non-fatal) |
| Missing environment variable | Raise `EnvironmentError` with a descriptive message (fatal) |
| Insufficient market data | Raise `ValueError` from `drawdown.py`, catch in `main.py` |
| State file read failure | Log warning, fall back to default state (never crash on read) |
| State file write failure | Raise `RuntimeError` (we must persist state) |

---

## Logging Standards

- Use Python's `logging` module exclusively — **never use `print()`**
- Configure at the root level in `main.py` only:
  ```python
  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
      handlers=[logging.StreamHandler(sys.stdout)],
  )
  ```
- Each module gets its own logger: `logger = logging.getLogger(__name__)`
- Log levels:
  - `DEBUG` — intermediate calculation values
  - `INFO` — flow control, final results, state transitions
  - `WARNING` — recoverable issues (e.g., missing optional data)
  - `ERROR` — failures that affect output (API errors, file errors)

---

## Environment Variables

All secrets are injected via environment variables. Never hardcode credentials.

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot API token from @BotFather |
| `TELEGRAM_CHAT_ID` | Target Telegram chat/channel ID |

Validate presence at the call site using `os.environ.get()` and raise `EnvironmentError` if missing.

---

## Extensibility Rules

- **Add a new asset**: Add a `TickerConfig` entry to `MONITORED_ASSETS` in `src/config.py`
- **Change drawdown thresholds**: Edit `DCA_LEVEL_THRESHOLDS` in `src/config.py`
- **Change DCA levels**: Edit `DCA_LEVELS` in `src/config.py`
- **Never** hardcode ticker symbols, thresholds, or level labels in business logic modules

---

## State Persistence

- State is stored in `state/state.json` as a JSON object keyed by ticker symbol
- After every state change, the file is committed and pushed by GitHub Actions
- The `[skip ci]` tag in commit messages prevents infinite workflow loops
- On first run (no state file), the app treats `last_level` as `None`

---

## GitHub Actions Specifics

- Workflow: `.github/workflows/monitor.yml`
- Schedule: daily at `0 20 * * *` (20:00 UTC) + `workflow_dispatch`
- The `contents: write` permission is required for state file commits
- Use `git diff --staged --quiet` before committing to avoid empty commits
- Use `[skip ci]` in automated commit messages

---

## Testing Considerations

- Business logic functions (`calculate_drawdown`, `get_dca_level`, `should_send_alert`) are pure functions — test them with unit tests and no mocks
- Side-effect modules (`data_fetcher`, `telegram_notifier`, `state_manager`) should be tested with mocks for external calls
- Use dependency injection where appropriate to keep functions testable
