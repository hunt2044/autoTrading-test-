from decimal import Decimal
from config.schema import get_settings

from src.core.enums import PositionSide, SignalAction
from src.core.models import Candle, Indicators, Signal


class MomentumTrendSignal:
    def __init__(self):
        settings = get_settings()
        mt = settings.momentum_trend if hasattr(settings, 'momentum_trend') else None
        self.rsi_pullback_low = mt.rsi_pullback_low if mt and hasattr(mt, 'rsi_pullback_low') else 45
        self.rsi_pullback_high = mt.rsi_pullback_high if mt and hasattr(mt, 'rsi_pullback_high') else 55
        self.volume_breakout_multiplier = Decimal(str(mt.volume_breakout_multiplier)) if mt and hasattr(mt, 'volume_breakout_multiplier') else Decimal("1.5")

    def generate(
        self,
        candle: Candle,
        indicators: Indicators,
        current_position: PositionSide,
    ) -> Signal | None:
        if (
            indicators.ema_short is None
            or indicators.ema_long is None
            or indicators.rsi is None
            or indicators.prev_rsi is None
            or indicators.volume_avg_20 is None
            or indicators.swing_high_20 is None
        ):
            return None

        ema_short = indicators.ema_short
        ema_long = indicators.ema_long
        rsi = indicators.rsi
        prev_rsi = indicators.prev_rsi
        volume_avg_20 = indicators.volume_avg_20
        swing_high_20 = indicators.swing_high_20

        trend_up = ema_short > ema_long and candle.close > ema_short and candle.close > ema_long

        if current_position == PositionSide.FLAT:
            if trend_up:
                if self.rsi_pullback_low <= prev_rsi <= self.rsi_pullback_high and rsi > prev_rsi:
                    return Signal(
                        action=SignalAction.ENTRY_LONG,
                        price=candle.open,
                        timestamp=candle.timestamp,
                        indicators=indicators,
                        strength=1.0,
                    )

                if candle.close > swing_high_20 and candle.volume > volume_avg_20 * self.volume_breakout_multiplier:
                    return Signal(
                        action=SignalAction.ENTRY_LONG,
                        price=candle.open,
                        timestamp=candle.timestamp,
                        indicators=indicators,
                        strength=1.0,
                    )

            return Signal(
                action=SignalAction.HOLD,
                price=candle.close,
                timestamp=candle.timestamp,
                indicators=indicators,
                strength=0.0,
            )

        if current_position == PositionSide.LONG:
            if candle.close < ema_long:
                return Signal(
                    action=SignalAction.EXIT_LONG,
                    price=candle.open,
                    timestamp=candle.timestamp,
                    indicators=indicators,
                    strength=1.0,
                )

            return Signal(
                action=SignalAction.HOLD,
                price=candle.close,
                timestamp=candle.timestamp,
                indicators=indicators,
                strength=0.0,
            )

        return Signal(
            action=SignalAction.HOLD,
            price=candle.close,
            timestamp=candle.timestamp,
            indicators=indicators,
            strength=0.0,
        )