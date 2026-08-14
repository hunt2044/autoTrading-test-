from dataclasses import dataclass
from decimal import Decimal

from config.schema import get_settings
from src.core.models import Candle, Indicators
from src.indicators.calculator import ATR, EMA, RSI, RollingAverage, RollingMax


@dataclass(slots=True)
class IndicatorState:
    ema_short: EMA
    ema_long: EMA
    atr: ATR
    rsi: RSI
    volume_avg_20: RollingAverage
    swing_high_20: RollingMax
    prev_ema_short: Decimal | None = None
    prev_ema_long: Decimal | None = None
    prev_rsi: Decimal | None = None


class IndicatorCalculator:
    def __init__(self):
        settings = get_settings()
        self.state = IndicatorState(
            ema_short=EMA(settings.ema_short),
            ema_long=EMA(settings.ema_long),
            atr=ATR(settings.atr_period),
            rsi=RSI(settings.rsi_period if hasattr(settings, 'rsi_period') else 14),
            volume_avg_20=RollingAverage(settings.volume_avg_period if hasattr(settings, 'volume_avg_period') else 20),
            swing_high_20=RollingMax(settings.swing_high_period if hasattr(settings, 'swing_high_period') else 20),
        )
        self.settings = settings

    def process_candle(self, candle: Candle) -> Indicators:
        self.state.prev_ema_short = self.state.ema_short.get()
        self.state.prev_ema_long = self.state.ema_long.get()
        self.state.prev_rsi = self.state.rsi.get()

        ema_short_val = self.state.ema_short.update(candle.close)
        ema_long_val = self.state.ema_long.update(candle.close)
        atr_val = self.state.atr.update(candle.high, candle.low, candle.close)
        rsi_val = self.state.rsi.update(candle.close)
        volume_avg_val = self.state.volume_avg_20.update(candle.volume)
        swing_high_val = self.state.swing_high_20.update(candle.high)

        return Indicators(
            ema_short=ema_short_val,
            ema_long=ema_long_val,
            atr=atr_val,
            prev_ema_short=self.state.prev_ema_short,
            prev_ema_long=self.state.prev_ema_long,
            rsi=rsi_val,
            prev_rsi=self.state.prev_rsi,
            volume_avg_20=volume_avg_val,
            swing_high_20=swing_high_val,
        )

    def reset(self) -> None:
        self.state.ema_short.reset()
        self.state.ema_long.reset()
        self.state.atr.reset()
        self.state.rsi.reset()
        self.state.volume_avg_20.reset()
        self.state.swing_high_20.reset()
        self.state.prev_ema_short = None
        self.state.prev_ema_long = None
        self.state.prev_rsi = None