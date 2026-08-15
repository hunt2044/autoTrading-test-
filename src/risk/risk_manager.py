from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from config.schema import get_settings
from src.core.models import Indicators


@dataclass(slots=True)
class RiskParams:
    quantity: Decimal
    stop_loss: Decimal
    risk_amount: Decimal


class RiskManager:
    def __init__(self):
        settings = get_settings()
        self.risk_per_trade_pct = Decimal(str(settings.risk_per_trade_pct))
        self.atr_multiplier = self._get_atr_multiplier(settings)

    def _get_atr_multiplier(self, settings) -> Decimal:
        if settings.strategy == "momentum_trend_1h":
            return Decimal(str(settings.momentum_trend.atr_multiplier))
        return Decimal(str(settings.atr_multiplier))

    def calculate_position_size(
        self,
        equity: Decimal,
        entry_price: Decimal,
        indicators: Indicators,
    ) -> RiskParams:
        if indicators.atr is None:
            raise ValueError("ATR not available for risk calculation")

        stop_loss = entry_price - (self.atr_multiplier * indicators.atr)

        if stop_loss >= entry_price:
            raise ValueError("Invalid stop loss: stop >= entry")

        risk_per_unit = entry_price - stop_loss
        risk_amount = equity * self.risk_per_trade_pct
        raw_quantity = risk_amount / risk_per_unit

        quantity = self._round_down_to_precision(raw_quantity)

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