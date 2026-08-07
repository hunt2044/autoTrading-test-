from decimal import Decimal


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