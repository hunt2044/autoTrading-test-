# Telegram Notifications Setup

## Overview
The system sends WARNING, ERROR, and CRITICAL log events to Telegram. INFO and DEBUG logs are filtered out to avoid spam.

## Prerequisites
1. A Telegram account
2. Create a bot via [@BotFather](https://t.me/BotFather):
   - Send `/newbot` to @BotFather
   - Follow prompts to name your bot
   - Save the **bot token** (format: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`)
3. Get your chat ID via [@userinfobot](https://t.me/userinfobot):
   - Send any message to @userinfobot
   - It replies with your numeric **chat ID**

## Configuration
Add to `.env` (copy from `.env.example`):

```bash
TELEGRAM__BOT_TOKEN=your_bot_token_here
TELEGRAM__CHAT_ID=your_chat_id_here
```

Both are optional. If either is unset, Telegram notifications are disabled (no errors).

## Behavior
- **Trigger**: Any log at WARNING level (30) or above
- **Format**: `[LEVEL] logger_name: message`
- **Delivery**: Best-effort via Telegram Bot API (HTTPS POST)
- **Timeout**: 5 seconds per request
- **Failure handling**: Network/API failures logged locally at DEBUG level; never crash the trading loop
- **No retries**: Failed deliveries are dropped silently (not critical path)

## Example Messages
```
[WARNING] src.live.runner: STOP LOSS TRIGGERED at 2850.42
[ERROR] src.execution.reconciler: Failed to sync account from Demo Mode: BinanceAPIError(500, "Internal Server Error")
[WARNING] src.live.runner: ALERT: No new candle received for 6 hours
[CRITICAL] src.live.runner: Order failed: Insufficient balance
```

## Testing
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

## Security Notes
- Bot token grants send-only access to your chat
- Store `.env` securely (already in `.gitignore`)
- Do not share bot token publicly
- Revoke token via @BotFather if compromised: `/revoke`