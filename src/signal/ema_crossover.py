from dataclasses import dataclass

from src.core.enums import PositionSide, SignalAction
from src.core.models import Candle, Indicators, Signal


@dataclass(slots=True)
class EmaCrossoverSignal:
    def generate(
        self,
        candle: Candle,
        indicators: Indicators,
        current_position: PositionSide,
    ) -> Signal | None:
        if (
            indicators.ema_short is None
            or indicators.ema_long is None
            or indicators.prev_ema_short is None
            or indicators.prev_ema_long is None
        ):
            return None

        prev_short = indicators.prev_ema_short
        prev_long = indicators.prev_ema_long
        curr_short = indicators.ema_short
        curr_long = indicators.ema_long

        was_below = prev_short <= prev_long
        is_above = curr_short > curr_long

        was_above = prev_short >= prev_long
        is_below = curr_short < curr_long

        if was_below and is_above and current_position == PositionSide.FLAT:
            return Signal(
                action=SignalAction.ENTRY_LONG,
                price=candle.open,
                timestamp=candle.timestamp,
                indicators=indicators,
                strength=1.0,
            )

        if was_above and is_below and current_position == PositionSide.LONG:
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