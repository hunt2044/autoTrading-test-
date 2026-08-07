from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.monitoring.logger import get_logger


@dataclass(slots=True)
class Alert:
    level: str
    message: str
    component: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = field(default_factory=dict)


class AlertManager:
    def __init__(self):
        self.logger = get_logger("alerts")
        self.alerts: list[Alert] = []
        self.alert_callbacks: list[callable] = []

    def add_callback(self, callback: callable) -> None:
        self.alert_callbacks.append(callback)

    def alert(self, level: str, message: str, component: str, **details: Any) -> None:
        alert = Alert(level=level, message=message, component=component, details=details)
        self.alerts.append(alert)

        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message, component=component, **details)

        for callback in self.alert_callbacks:
            with suppress(Exception):
                callback(alert)

    def info(self, message: str, component: str, **details: Any) -> None:
        self.alert("INFO", message, component, **details)

    def warning(self, message: str, component: str, **details: Any) -> None:
        self.alert("WARNING", message, component, **details)

    def error(self, message: str, component: str, **details: Any) -> None:
        self.alert("ERROR", message, component, **details)

    def critical(self, message: str, component: str, **details: Any) -> None:
        self.alert("CRITICAL", message, component, **details)

    def check_missing_candle(self, last_candle_time: datetime | None, threshold_hours: int) -> bool:
        if last_candle_time is None:
            return False

        now = datetime.now(UTC)
        hours_since = (now - last_candle_time).total_seconds() / 3600

        if hours_since > threshold_hours:
            self.warning(
                f"No new candle for {hours_since:.1f} hours (threshold: {threshold_hours}h)",
                "data_feed",
                last_candle_time=last_candle_time.isoformat(),
                hours_since=hours_since,
            )
            return True
        return False

    def check_order_rejected(self, order_id: str, symbol: str, error: str) -> None:
        self.error(
            f"Order rejected: {error}",
            "execution",
            order_id=order_id,
            symbol=symbol,
        )

    def check_reconciliation_mismatch(self, discrepancies: list[str]) -> None:
        self.warning(
            f"Reconciliation mismatch: {len(discrepancies)} discrepancies",
            "reconciliation",
            discrepancies=discrepancies,
        )

    def check_demo_maintenance(self, is_maintenance: bool) -> None:
        if is_maintenance:
            self.warning(
                "Binance Demo Mode under maintenance",
                "exchange",
            )

    def get_recent_alerts(self, limit: int = 100) -> list[Alert]:
        return self.alerts[-limit:]

    def clear_alerts(self) -> None:
        self.alerts.clear()


_alert_manager: AlertManager | None = None


def get_alert_manager() -> AlertManager:
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager