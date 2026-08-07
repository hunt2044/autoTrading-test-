import sys
from pathlib import Path
from typing import Any

from loguru import logger

from config.schema import get_settings


def setup_logging() -> None:
    settings = get_settings()
    log_file = Path(settings.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    logger.add(
        log_file,
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
    )

    logger.add(
        log_file.with_suffix(".json"),
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {function} | {line} | {message}",
        serialize=True,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
    )


def get_logger(name: str):
    return logger.bind(module=name)


class TradingLogger:
    def __init__(self, name: str):
        self.logger = get_logger(name)

    def log_candle(self, candle: Any) -> None:
        self.logger.info(
            "Candle received",
            symbol=candle.symbol,
            interval=candle.interval,
            timestamp=candle.timestamp.isoformat(),
            open=str(candle.open),
            high=str(candle.high),
            low=str(candle.low),
            close=str(candle.close),
            volume=str(candle.volume),
            source=candle.source.value,
        )

    def log_signal(self, signal: Any, position_side: str) -> None:
        self.logger.info(
            "Signal generated",
            action=signal.action.value,
            price=str(signal.price),
            timestamp=signal.timestamp.isoformat(),
            position_side=position_side,
            ema_short=str(signal.indicators.ema_short) if signal.indicators.ema_short else None,
            ema_long=str(signal.indicators.ema_long) if signal.indicators.ema_long else None,
            atr=str(signal.indicators.atr) if signal.indicators.atr else None,
        )

    def log_order(self, order: Any, success: bool, error: str | None = None) -> None:
        self.logger.info(
            "Order placed",
            order_id=order.id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side.value,
            type=order.type.value,
            quantity=str(order.quantity),
            price=str(order.price) if order.price else None,
            success=success,
            error=error,
        )

    def log_position_change(self, position: Any, reason: str) -> None:
        self.logger.info(
            "Position changed",
            symbol=position.symbol,
            side=position.side,
            quantity=str(position.quantity),
            entry_price=str(position.entry_price) if position.entry_price else None,
            stop_loss=str(position.stop_loss) if position.stop_loss else None,
            reason=reason,
        )

    def log_reconciliation(self, matched: bool, discrepancies: list[str]) -> None:
        if matched:
            self.logger.info("Reconciliation OK")
        else:
            self.logger.warning(
                "Reconciliation mismatch",
                discrepancies=discrepancies,
            )

    def log_equity(self, equity: Any, available_balance: Any, position_value: Any = None) -> None:
        self.logger.info(
            "Equity update",
            total_equity=str(equity),
            available_balance=str(available_balance),
            position_value=str(position_value) if position_value else None,
        )

    def log_error(self, message: str, **kwargs: Any) -> None:
        self.logger.error(message, **kwargs)

    def log_warning(self, message: str, **kwargs: Any) -> None:
        self.logger.warning(message, **kwargs)

    def log_info(self, message: str, **kwargs: Any) -> None:
        self.logger.info(message, **kwargs)