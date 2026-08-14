from typing import Protocol

from src.core.enums import PositionSide, SignalAction
from src.core.models import Candle, Indicators, Signal
from src.signal.ema_crossover import EmaCrossoverSignal
from src.signal.momentum_trend import MomentumTrendSignal


class SignalGenerator(Protocol):
    def generate(
        self,
        candle: Candle,
        indicators: Indicators,
        current_position: PositionSide,
    ) -> Signal | None: ...


_STRATEGY_REGISTRY = {
    "ema_crossover": EmaCrossoverSignal,
    "momentum_trend_1h": MomentumTrendSignal,
}


def create_signal_generator(strategy_name: str) -> SignalGenerator:
    if strategy_name not in _STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. Available: {list(_STRATEGY_REGISTRY)}"
        )
    return _STRATEGY_REGISTRY[strategy_name]()


__all__ = ["EmaCrossoverSignal", "MomentumTrendSignal", "SignalGenerator", "create_signal_generator"]