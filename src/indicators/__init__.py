from dataclasses import dataclass
from decimal import Decimal

from config.schema import get_settings
from src.core.models import Candle, Indicators
from src.indicators.calculator import ATR, EMA


@dataclass(slots=True)
class IndicatorState:
    ema_short: EMA
    ema_long: EMA
    atr: ATR
    prev_ema_short: Decimal | None = None
    prev_ema_long: Decimal | None = None


class IndicatorCalculator:
    def __init__(self):
        settings = get_settings()
        self.state = IndicatorState(
            ema_short=EMA(settings.ema_short),
            ema_long=EMA(settings.ema_long),
            atr=ATR(settings.atr_period),
        )
        self.settings = settings

    def process_candle(self, candle: Candle) -> Indicators:
        self.state.prev_ema_short = self.state.ema_short.get()
        self.state.prev_ema_long = self.state.ema_long.get()

        ema_short_val = self.state.ema_short.update(candle.close)
        ema_long_val = self.state.ema_long.update(candle.close)
        atr_val = self.state.atr.update(candle.high, candle.low, candle.close)

        return Indicators(
            ema_short=ema_short_val,
            ema_long=ema_long_val,
            atr=atr_val,
            prev_ema_short=self.state.prev_ema_short,
            prev_ema_long=self.state.prev_ema_long,
        )

    def reset(self) -> None:
        self.state.ema_short.reset()
        self.state.ema_long.reset()
        self.state.atr.reset()
        self.state.prev_ema_short = None
        self.state.prev_ema_long = None