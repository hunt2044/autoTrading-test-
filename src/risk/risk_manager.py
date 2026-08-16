from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from config.schema import get_settings
from src.core.models import Indicators
from src.monitoring.logger import get_logger


logger = get_logger(__name__)


@dataclass(slots=True)
class RiskParams:
    quantity: Decimal
    stop_loss: Decimal
    risk_amount: Decimal


class RiskManager:
    def __init__(self):
        settings = get_settings()
        self.risk_per_trade_pct = self._get_risk_per_trade_pct(settings)
        self.max_position_pct_of_equity = Decimal(str(settings.max_position_pct_of_equity))
        self.atr_floor_pct = Decimal(str(settings.atr_floor_pct))
        self.atr_multiplier = self._get_atr_multiplier(settings)

    def _get_atr_multiplier(self, settings) -> Decimal:
        if settings.strategy == "momentum_trend_1h":
            return Decimal(str(settings.momentum_trend.atr_multiplier))
        return Decimal(str(settings.atr_multiplier))

    def _get_risk_per_trade_pct(self, settings) -> Decimal:
        if settings.strategy == "momentum_trend_1h":
            return Decimal(str(settings.momentum_trend.risk_per_trade_pct))
        return Decimal(str(settings.risk_per_trade_pct))

    def calculate_position_size(
        self,
        equity: Decimal,
        entry_price: Decimal,
        indicators: Indicators,
        available_balance: Decimal | None = None,
    ) -> RiskParams:
        if indicators.atr is None:
            raise ValueError("ATR not available for risk calculation")

        # Apply ATR floor: use max of real ATR and price-based floor
        min_atr = entry_price * self.atr_floor_pct
        effective_atr = max(indicators.atr, min_atr)
        if effective_atr > indicators.atr:
            logger.info(
                "ATR floor applied: raw atr={} below floor {} ({:.2%} of price {}), using floor",
                indicators.atr, min_atr, self.atr_floor_pct, entry_price,
            )

        stop_loss = entry_price - (self.atr_multiplier * effective_atr)

        if stop_loss >= entry_price:
            raise ValueError("Invalid stop loss: stop >= entry")

        risk_per_unit = entry_price - stop_loss
        risk_amount = equity * self.risk_per_trade_pct
        raw_quantity = risk_amount / risk_per_unit

        quantity = self._round_down_to_precision(raw_quantity)

        # Cap quantity by available balance (95% margin for fees/slippage)
        if available_balance is not None and available_balance > Decimal("0"):
            max_affordable_notional = available_balance * Decimal("0.95")
            max_affordable_qty = self._round_down_to_precision(max_affordable_notional / entry_price)
            if quantity > max_affordable_qty:
                logger.warning(
                    "Position size capped by available balance: {} -> {} "
                    "(notional would be {}, available={})",
                    quantity, max_affordable_qty, quantity * entry_price, available_balance,
                )
                quantity = max_affordable_qty

        # Cap position size by max fraction of available balance (safety net)
        if available_balance is not None and available_balance > Decimal("0"):
            max_position_notional = available_balance * self.max_position_pct_of_equity
            notional = quantity * entry_price
            if notional > max_position_notional:
                logger.warning(
                    "Signal rejected: risk-based position size would use {:.1%} of "
                    "available balance (notional={}, limit={:.1%} = {}), atr={}",
                    notional / available_balance,
                    notional,
                    self.max_position_pct_of_equity,
                    max_position_notional,
                    indicators.atr,
                )
                raise ValueError("Position size exceeds max allowed fraction of equity")

        if quantity <= 0:
            raise ValueError("Calculated quantity is zero or negative")

        return RiskParams(
            quantity=quantity,
            stop_loss=stop_loss,
            risk_amount=risk_amount,
        )

    def _round_down_to_precision(self, value: Decimal, precision: int = 6) -> Decimal:
        quantizer = Decimal("0.1") ** precision
        return (value / quantizer).quantize(Decimal("1"), rounding=ROUND_DOWN) * quantizer