# 📈 Index Opportunity Alerts

Automated Python application that monitors the **QQQ ETF (Nasdaq-100)** daily and generates dynamic **Dollar-Cost Averaging (DCA) investment signals** based on market drawdowns. Alerts are delivered via **Telegram** and the entire system runs hands-free on **GitHub Actions**.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [How It Works](#how-it-works)
3. [Drawdown Logic](#drawdown-logic)
4. [DCA Strategy & Signal Levels](#dca-strategy--signal-levels)
5. [State Persistence](#state-persistence)
6. [Project Structure](#project-structure)
7. [Installation & Local Execution](#installation--local-execution)
8. [GitHub Secrets Setup](#github-secrets-setup)
9. [GitHub Actions Workflow](#github-actions-workflow)
10. [Adding More Assets](#adding-more-assets)
11. [Error Handling](#error-handling)

---

## Project Overview

This tool answers a simple question every trading day:

> *"Is this a good time to invest more than usual?"*

It does this by calculating how far the QQQ ETF has fallen from its recent peaks over multiple time windows (30, 60, 90, and 180 trading days). When the market dips meaningfully, it sends a Telegram message with a suggested DCA multiplier.

**No manual monitoring needed.** The workflow runs automatically after US market close (20:00 UTC) every day.

---

## Investment Philosophy

> *"Time in the market beats timing the market — but size matters when the market is on sale."*

Because indexes like QQQ trend **upward over the long run**, the default strategy is simply to invest a fixed amount regularly (DCA). This system does **not** try to predict tops or bottoms.

What it *does* do is answer a relative question: **"Compared to where this index recently was, is it cheaper than usual today?"**

When the answer is yes, you have a temporary opportunity to deploy more capital than normal — not instead of your regular DCA, but **on top of it**.

This means:

- **Level 0 (healthy)** is the expected, normal state. Silence = no action needed.
- Drawdowns happen regularly even in bull markets (2018: −23 %, 2020: −27 %, 2022: −35 %).
- After every historical drawdown, QQQ recovered and made new highs. That recovery is what makes the extra deployment profitable.
- The signal resets every time QQQ makes a new high — so if all four windows show the same drawdown, it means the all-time high within that window was very recent. That is expected behaviour in an uptrending market.

**The system is not a sell signal.** It never tells you to exit. It only tells you when a dip is worth extra buying.

---

## How It Works

```
Daily at 20:00 UTC
       │
       ▼
┌─────────────────────┐
│  Fetch price data   │  yfinance — last ~300 calendar days of QQQ
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Flash crash check  │  daily close-to-close drop ≥ 5%?
└────────┬────────────┘
         │ yes → ⚡ send flash crash alert (no state, always fires)
         │
         ▼
┌─────────────────────┐
│ Calculate drawdowns │  5d, 30d, 60d, 90d, 180d windows
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Pick worst dd      │  reference = min(dd_5, dd_30, dd_60, dd_90, dd_180)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Map to DCA level   │  0 (healthy) → 5 (crash)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Compare to state   │  Load last level from state/state.json
└────────┬────────────┘
         │ level changed?
    Yes  │              No
    ─────┼─────          │
    │         │          └── do nothing
    ▼         │
Send Telegram │
DCA alert     │
    │         │
    ▼         │
Update &      │
commit state──┘
```

---

## Drawdown Logic

For each time window $N$ (30, 60, 90, or 180 trading days):

$$\text{drawdown}_N = \frac{\text{current\_price} - \max(\text{close}_{-N \ldots 0})}{\max(\text{close}_{-N \ldots 0})} \times 100$$

The **reference drawdown** used for signalling is the **worst** (most negative) across all windows:

$$\text{reference} = \min(\text{drawdown}_{5},\ \text{drawdown}_{30},\ \text{drawdown}_{60},\ \text{drawdown}_{90},\ \text{drawdown}_{180})$$

The **5-day window** catches fast crashes (like COVID's −27 % in a single week) that might not yet show in longer windows. The longer windows catch slow-building bear markets.

**Example:**

| Window | Max price | Current price | Drawdown |
|--------|-----------|---------------|-----------|
| 5 d    | $462      | $460          | −0.4 %   |
| 30 d   | $480      | $460          | −4.2 %   |
| 60 d   | $495      | $460          | **−7.1 %** ← reference |
| 90 d   | $490      | $460          | −6.1 %   |
| 180 d  | $470      | $460          | −2.1 %   |

→ Reference drawdown = **−7.1 %** → **Level 1 (Mild Dip)**

---

## DCA Strategy & Signal Levels

| Level | Label        | Drawdown threshold | Multiplier | Action |
|-------|--------------|--------------------|------------|--------|
| 0     | ✅ HEALTHY   | > −5 %             | —          | Keep regular DCA schedule |
| 1     | 🟡 MILD DIP  | −5 % to −10 %      | **1.5×**   | Slightly increase contribution |
| 2     | 🟠 MODERATE DIP | −10 % to −15 %  | **2×**     | Double your regular DCA |
| 3     | 🔴 MAJOR DIP | −15 % to −20 %     | **3×**     | Aggressive top-up |
| 4     | 🆘 SEVERE DIP | −20 % to −30 %    | **4×**     | Major buying opportunity |
| 5     | 💥 CRASH     | < −30 %             | **5×**     | Maximum DCA deployment |

### Alert rules

- **Level unchanged** → no message (silence = no action needed)
- **Level increases** → alert: drawdown is deepening, increase DCA
- **Level decreases** → alert: market is recovering
- **Recovery to Level 0** → alert: back to healthy, resume normal schedule
- **First run with Level 0** → no message (nothing to act on)

All thresholds are configurable in `src/config.py` — no business logic needs to change.

### ⚡ Flash Crash Alerts

In addition to the DCA level system, a **separate independent alert** fires when a single trading day's close-to-close drop equals or exceeds **−5 %**:

| Property | Value |
|---|---|
| Trigger | Daily close-to-close drop ≤ −5 % |
| Threshold | Configurable via `FLASH_CRASH_DAILY_THRESHOLD` in `src/config.py` |
| State gating | **None** — fires every day the threshold is breached |
| Purpose | Catch fast crashes (e.g. COVID week 1) before they register in longer drawdown windows |

Both alerts can fire on the same run: a −6 % day would send the flash crash alert **and** potentially trigger a DCA level change alert.

---

## State Persistence

State is stored in `state/state.json`, committed to this repository after every run by GitHub Actions:

```json
{
  "QQQ": {
    "last_level": 2,
    "last_drawdown": -11.34,
    "last_updated": "2026-06-12T20:05:43.123456+00:00"
  }
}
```

**Why commit state to the repo?**

GitHub Actions runners are ephemeral — each job starts from a clean environment. Committing state to the repository is the simplest, dependency-free way to persist it across daily runs without needing an external database or object storage.

The automated commit uses `[skip ci]` in its message to prevent an infinite workflow trigger loop.

---

## Project Structure

```
.
├── main.py                      # Orchestration entry point
├── requirements.txt
├── state/
│   ├── .gitkeep
│   └── state.json               # Auto-generated on first run
├── src/
│   ├── __init__.py
│   ├── config.py                # ← Edit here to add assets / change thresholds
│   ├── data_fetcher.py          # Yahoo Finance integration
│   ├── drawdown.py              # Pure drawdown calculation functions
│   ├── signals.py               # Level mapping and alert decision logic
│   ├── state_manager.py         # JSON state read / write
│   └── telegram_notifier.py     # Telegram Bot API client
├── .github/
│   ├── copilot-instructions.md  # AI coding guidelines for this project
│   └── workflows/
│       └── monitor.yml          # Daily GitHub Actions workflow
└── docs/
    └── TELEGRAM_BOT.md          # Step-by-step Telegram setup guide
```

---

## Installation & Local Execution

### Prerequisites

- Python 3.11+
- A Telegram bot token and chat ID (see [docs/TELEGRAM_BOT.md](docs/TELEGRAM_BOT.md))

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/index-opportunity-alerts.git
cd index-opportunity-alerts
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set environment variables

```bash
export TELEGRAM_BOT_TOKEN="123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export TELEGRAM_CHAT_ID="987654321"
```

On Windows (PowerShell):

```powershell
$env:TELEGRAM_BOT_TOKEN = "123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:TELEGRAM_CHAT_ID   = "987654321"
```

### 5. Run the application

```bash
python main.py
```

Expected output (no level change):

```
2026-06-12 20:00:01 [INFO] __main__: Index Opportunity Alerts — run started
2026-06-12 20:00:01 [INFO] __main__: ============================================================
2026-06-12 20:00:01 [INFO] __main__: Processing: Nasdaq-100 ETF (QQQ) (QQQ)
2026-06-12 20:00:03 [INFO] src.data_fetcher: Fetched 207 trading days for QQQ — latest close: $478.32
2026-06-12 20:00:03 [INFO] src.drawdown: Reference drawdown: -3.45% (from 60-day window)
2026-06-12 20:00:03 [INFO] src.signals: Level change check: 0 → 0 → send alert: False
2026-06-12 20:00:03 [INFO] __main__: Level unchanged (0). No alert dispatched for QQQ.
2026-06-12 20:00:03 [INFO] __main__: All assets processed successfully.
```

---

## GitHub Secrets Setup

Add the following secrets to your repository:

**Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your chat / channel ID |

> For detailed instructions on obtaining these values, see [docs/TELEGRAM_BOT.md](docs/TELEGRAM_BOT.md).

`GITHUB_TOKEN` is provided automatically by GitHub Actions — no manual setup required.

---

## GitHub Actions Workflow

The workflow file is at [.github/workflows/monitor.yml](.github/workflows/monitor.yml).

| Property | Value |
|---|---|
| Schedule | Daily at **20:00 UTC** (after NYSE close) |
| Manual trigger | ✅ `workflow_dispatch` |
| Runner | `ubuntu-latest` |
| Timeout | 10 minutes |
| Python version | 3.11 |
| State commit | Automatic, `[skip ci]` |

### Manual trigger

Go to **Actions → Index Opportunity Monitor → Run workflow** to trigger a run on demand.

---

## Adding More Assets

Open `src/config.py` and add a new entry to `MONITORED_ASSETS`:

```python
MONITORED_ASSETS: list[TickerConfig] = [
    TickerConfig(symbol="QQQ", name="Nasdaq-100 ETF (QQQ)"),
    TickerConfig(symbol="SPY", name="S&P 500 ETF (SPY)"),
    TickerConfig(symbol="IWM", name="Russell 2000 ETF (IWM)"),
    # Any Yahoo Finance-supported symbol works here
    TickerConfig(symbol="AAPL", name="Apple Inc."),
]
```

Each asset gets its own entry in `state/state.json` and independent alert tracking. No other file needs to change.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Yahoo Finance API failure | Logged as ERROR; asset skipped; other assets continue |
| Insufficient price history | Logged as ERROR; asset skipped |
| Telegram send failure | Logged as ERROR; **state not updated** (alert retried next run) |
| Missing `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | `EnvironmentError` raised; entire run aborted immediately |
| State file unreadable | Logged as WARNING; defaults used (no crash) |
| State file write failure | `RuntimeError` raised; asset marked as failed |
| Any unhandled exception | Logged with full traceback; asset marked as failed |

The GitHub Actions job exits with code `1` if any asset fails, making the failure visible in the Actions UI.

---

## License

[MIT](LICENSE)
