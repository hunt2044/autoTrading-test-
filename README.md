# ETH 4H MVP Trading System

Automated paper trading system for ETH/USDT on 4-hour timeframe using Binance Demo Mode.

> [!NOTE]
> This is a vibe-coded project for learning purposes about CI/CD on cloud. Not recommended for production use.

## Features

- **EMA Crossover Strategy**: EMA(20) / EMA(50) crossover on 4h candles
- **Risk Management**: 1% risk per trade, ATR(14) × 2 stop-loss
- **Paper Trading**: Binance Demo Mode (no real funds)
- **Backtesting**: Historical data from Binance mainnet
- **Data Storage**: Parquet/CSV/SQLite for candle data
- **Monitoring**: Structured JSON logging, alerts, reconciliation

## Quick Start

### Installation

```bash
# Clone and install
git clone <repo-url>
cd eth_4h_mvp
pip install -e ".[dev]"

# Or with Poetry
poetry install
```

> [!NOTE]
> Use `venv` when running on Linux.

### Configuration

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your Binance Demo Mode API credentials:

   ```
   BINANCE__API_KEY=your_demo_api_key
   BINANCE__API_SECRET=your_demo_api_secret
   ```

   Get these from [demo.binance.com](https://demo.binance.com/en/my/settings/api-management) after enabling Demo Trading on your main Binance account.

   **Note**: The config uses `env_nested_delimiter="__"`, so nested settings require double underscore (e.g., `BINANCE__API_KEY`, not `BINANCE_DEMO_API_KEY`).

3. Adjust `config/settings.yaml` if needed (strategy params, risk, logging, etc.)

## Usage

### Fetch Historical Data (for backtesting)

```bash
# Fetch 3 years of 4h candles
python main.py fetch-history --years 3

# Fetch with custom date range
python main.py fetch-history --years 1
```

Data is stored in `data/` as Parquet files (separate files for backtest vs live sources).

### Run Backtest

```bash
# Default: last 3 years
python main.py backtest

# Custom date range
python main.py backtest --start 2023-01-01 --end 2024-01-01

# Custom output directory
python main.py backtest --output ./my_results
```

Outputs:

- `trades.csv` - All executed trades with PnL
- `equity_curve.csv` - Equity over time
- Console summary with metrics (Sharpe, max drawdown, win rate, profit factor)

### Live Paper Trading

```bash
python main.py live
```

The runner:

- Wakes up at each 4h candle close (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC)
- Fetches the latest closed candle from Demo Mode
- Generates signals, calculates position size, places orders
- Reconciles local state with Demo Mode account
- Logs all activity to `logs/trading.log`

Press `Ctrl+C` for graceful shutdown (cancels open orders).

### Configuration Commands

```bash
# Validate config file
python main.py validate-config

# Show current effective configuration
python main.py show-config
```

## Project Structure

```
eth_4h_mvp/
├── config/
│   ├── settings.yaml          # Main configuration
│   └── schema.py              # Pydantic settings with YAML/env loading
├── src/
│   ├── core/                  # Models, enums, config
│   ├── data/                  # Binance client, candle storage
│   ├── indicators/            # Incremental EMA, ATR
│   ├── signal/                # EMA crossover logic
│   ├── risk/                  # Position sizing, stop-loss
│   ├── execution/             # Order management, reconciliation
│   ├── backtest/              # Event-driven backtest engine
│   ├── live/                  # Live paper trading loop
│   ├── monitoring/            # Logging, alerting
│   └── cli/                   # Typer CLI commands
├── data/                      # Candle storage (gitignored)
├── logs/                      # Log files (gitignored)
├── results/                   # Backtest output (gitignored)
├── .env.example               # Environment template
├── .gitignore
├── main.py                    # Entry point
├── pyproject.toml
└── README.md
```

## Strategy Details

| Component         | Specification                                            |
| ----------------- | -------------------------------------------------------- |
| **Symbol**        | ETH/USDT (spot)                                          |
| **Timeframe**     | 4-hour candles                                           |
| **Direction**     | Long only (no short, no leverage)                        |
| **Entry**         | EMA(20) crosses above EMA(50) on close → enter next open |
| **Exit**          | EMA(20) crosses below EMA(50) on close → exit next open  |
| **Stop Loss**     | Entry − 2 × ATR(14) (fixed at entry)                     |
| **Risk/Trade**    | 1% of current equity                                     |
| **Position Size** | (0.01 × equity) / (entry − stop)                         |
| **Pyramiding**    | None (single position)                                   |
| **Fees**          | 0.1% taker (configurable)                                |
| **Slippage**      | 5 bps (configurable)                                     |

### Equity Calculation

- Equity = available_balance + unrealized_pnl
- Unrealized PnL = (current_price − entry_price) × quantity
- Equity updates each candle for drawdown/Sharpe calculation

## Data Sources

| Mode     | Source                 | Auth          | Purpose                           |
| -------- | ---------------------- | ------------- | --------------------------------- |
| Backtest | `api.binance.com`      | None (public) | Historical klines                 |
| Live     | `demo-api.binance.com` | Demo API key  | Real-time klines, orders, account |

**Important**: Demo Mode prices/liquidity may differ from production. Balance can reset anytime via Binance UI.

## Configuration Reference

Key settings in `config/settings.yaml`:

```yaml
mode: "backtest" # backtest | live
symbol: "ETHUSDT"
interval: "4h"
initial_capital: 10000.0

ema_short: 20
ema_long: 50
atr_period: 14
atr_multiplier: 2.0
risk_per_trade_pct: 0.01

backtest:
  fee_rate: 0.001 # 0.1%
  slippage_bps: 5 # 5 bps

live:
  alert_missing_candle_hours: 6
  reconciliation_tolerance: 0.0001

storage_format: "parquet" # parquet | csv | sqlite
```

## Monitoring & Logs

- **Console**: Colorized human-readable logs
- **File**: `logs/trading.log` (rotated, 30-day retention)
- **JSON**: `logs/trading.log.json` (structured for log aggregation)
- **Telegram**: Optional WARNING+ notifications (see below)

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

### Telegram Notifications (Optional)

Receive real-time WARNING/ERROR/CRITICAL alerts in Telegram.

#### Setup

1. Create a bot via [@BotFather](https://t.me/BotFather):
   - Send `/newbot` to @BotFather
   - Follow prompts to name your bot
   - Save the **bot token** (format: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`)
2. Get your chat ID via [@userinfobot](https://t.me/userinfobot):
   - Send any message to @userinfobot
   - It replies with your numeric **chat ID**
3. Add to `.env`:
   ```
   TELEGRAM__BOT_TOKEN=your_bot_token
   TELEGRAM__CHAT_ID=your_chat_id
   ```

Both are optional. If either is unset, Telegram notifications are disabled (no errors).

#### Behavior

- **Trigger**: Any log at WARNING level (30) or above
- **Format**: `[LEVEL] logger_name: message`
- **Delivery**: Best-effort via Telegram Bot API (HTTPS POST, 5s timeout)
- **Failure handling**: Network/API failures logged locally at DEBUG level; never crash the trading loop
- **No retries**: Failed deliveries are dropped silently (not critical path)

#### Example Messages

```
[WARNING] src.live.runner: STOP LOSS TRIGGERED at 2850.42
[ERROR] src.execution.reconciler: Failed to sync account from Demo Mode: BinanceAPIError(500, "Internal Server Error")
[WARNING] src.live.runner: ALERT: No new candle received for 6 hours
[CRITICAL] src.live.runner: Order failed: Insufficient balance
```

#### Testing

```bash
# With credentials set, trigger a warning
python -c "
from src.monitoring.logger import setup_logging
from loguru import logger
setup_logging()
logger.warning('Test Telegram alert')
"
```

Check your Telegram chat — message should arrive within seconds.

#### Security Notes

- Bot token grants send-only access to your chat
- Store `.env` securely (already in `.gitignore`)
- Do not share bot token publicly
- Revoke token via @BotFather if compromised: `/revoke`

### Alerts (via logs)

- Missing candles beyond threshold
- Order rejections
- Reconciliation mismatches
- Demo Mode maintenance

### Graceful Shutdown (SIGTERM)

The live runner handles `SIGTERM` (sent by `systemctl stop/restart`) for graceful shutdown:

- On `SIGTERM`: logs "SIGTERM received, shutting down gracefully...", cancels all open orders via `OrderManager`, closes the Binance client connection, then exits
- Uses `threading.Event.wait()` instead of `time.sleep()` for instant wake-up on shutdown signal (no up-to-1-hour delay)
- `Ctrl+C` (`SIGINT`) still works for manual interruption during development

For systemd deployments, this ensures `systemctl restart eth-4h-mvp` performs a clean handover without leaving orphan orders.

## Development

### Code Quality

```bash
# Lint
ruff check src/

# Format
ruff format src/

# Type check
mypy src/

# Tests
pytest
```

### Adding a New Indicator

1. Create `src/indicators/your_indicator.py`
2. Implement incremental `update()` method
3. Add to `IndicatorCalculator` in `src/indicators/__init__.py`
4. Use in signal/risk logic

### Adding a New Strategy

1. Create signal generator in `src/signal/`
2. Implement `generate(candle, indicators, position) -> Signal | None`
3. Wire into backtest engine and live runner

## Important Notes

⚠️ **Demo Mode Limitations**

- Prices may not match production exactly
- Balance resets possible at any time via Binance UI
- Not a guarantee of live performance

⚠️ **Not Financial Advice**
This is an educational/research MVP. No real funds at risk. Strategy is not optimized for profit.

⚠️ **Before Live Capital**

- [ ] Define max drawdown kill-switch
- [ ] Validate Demo Mode fee simulation
- [ ] Confirm default virtual balance
- [ ] Test funding rate filter (if added)
- [ ] Run extended paper trading period
