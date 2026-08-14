from decimal import Decimal
from collections import deque


class EMA:
    def __init__(self, period: int):
        if period < 1:
            raise ValueError("Period must be >= 1")
        self.period = period
        self.alpha = Decimal(2) / Decimal(period + 1)
        self.value: Decimal | None = None

    def update(self, price: Decimal) -> Decimal:
        if self.value is None:
            self.value = price
        else:
            self.value = self.alpha * price + (Decimal(1) - self.alpha) * self.value
        return self.value

    def get(self) -> Decimal | None:
        return self.value

    def reset(self) -> None:
        self.value = None


class ATR:
    def __init__(self, period: int):
        if period < 1:
            raise ValueError("Period must be >= 1")
        self.period = period
        self.alpha = Decimal(2) / Decimal(period + 1)
        self.value: Decimal | None = None
        self.prev_close: Decimal | None = None

    def update(self, high: Decimal, low: Decimal, close: Decimal) -> Decimal:
        true_range = self._true_range(high, low, close)
        if self.value is None:
            self.value = true_range
        else:
            self.value = self.alpha * true_range + (Decimal(1) - self.alpha) * self.value
        self.prev_close = close
        return self.value

    def _true_range(self, high: Decimal, low: Decimal, close: Decimal) -> Decimal:
        if self.prev_close is None:
            return high - low
        tr1 = high - low
        tr2 = abs(high - self.prev_close)
        tr3 = abs(low - self.prev_close)
        return max(tr1, tr2, tr3)

    def get(self) -> Decimal | None:
        return self.value

    def reset(self) -> None:
        self.value = None
        self.prev_close = None


class RSI:
    def __init__(self, period: int):
        if period < 1:
            raise ValueError("Period must be >= 1")
        self.period = period
        self.alpha = Decimal(1) / Decimal(period)
        self.prev_close: Decimal | None = None
        self.avg_gain: Decimal | None = None
        self.avg_loss: Decimal | None = None
        self._initialized = False

    def update(self, close: Decimal) -> Decimal | None:
        if self.prev_close is None:
            self.prev_close = close
            return None

        change = close - self.prev_close
        gain = max(change, Decimal(0))
        loss = max(-change, Decimal(0))

        if not self._initialized:
            self.avg_gain = gain
            self.avg_loss = loss
            self._initialized = True
        else:
            self.avg_gain = self.alpha * gain + (Decimal(1) - self.alpha) * self.avg_gain
            self.avg_loss = self.alpha * loss + (Decimal(1) - self.alpha) * self.avg_loss

        self.prev_close = close

        if self.avg_loss == 0:
            return Decimal(100)
        rs = self.avg_gain / self.avg_loss
        return Decimal(100) - (Decimal(100) / (Decimal(1) + rs))

    def get(self) -> Decimal | None:
        if self.avg_loss is None:
            return None
        if self.avg_loss == 0:
            return Decimal(100)
        rs = self.avg_gain / self.avg_loss
        return Decimal(100) - (Decimal(100) / (Decimal(1) + rs))

    def reset(self) -> None:
        self.prev_close = None
        self.avg_gain = None
        self.avg_loss = None
        self._initialized = False


class RollingAverage:
    def __init__(self, period: int):
        if period < 1:
            raise ValueError("Period must be >= 1")
        self.period = period
        self.values = deque(maxlen=period)
        self.sum = Decimal(0)

    def update(self, value: Decimal) -> Decimal | None:
        if len(self.values) == self.period:
            self.sum -= self.values[0]
        self.values.append(value)
        self.sum += value
        if len(self.values) < self.period:
            return None
        return self.sum / Decimal(self.period)

    def get(self) -> Decimal | None:
        if len(self.values) < self.period:
            return None
        return self.sum / Decimal(self.period)

    def reset(self) -> None:
        self.values.clear()
        self.sum = Decimal(0)


class RollingMax:
    def __init__(self, period: int):
        if period < 1:
            raise ValueError("Period must be >= 1")
        self.period = period
        self.values = deque(maxlen=period)

    def update(self, value: Decimal) -> Decimal | None:
        if len(self.values) == self.period:
            pass
        self.values.append(value)
        if len(self.values) < self.period:
            return None
        return max(self.values)

    def get(self) -> Decimal | None:
        if len(self.values) < self.period:
            return None
        return max(self.values)

    def reset(self) -> None:
        self.values.clear()