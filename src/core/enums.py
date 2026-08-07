from enum import StrEnum


class Mode(StrEnum):
    BACKTEST = "backtest"
    LIVE = "live"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(StrEnum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PositionSide(StrEnum):
    LONG = "LONG"
    FLAT = "FLAT"


class DataSource(StrEnum):
    BACKTEST = "backtest"
    LIVE = "live"


class SignalAction(StrEnum):
    ENTRY_LONG = "ENTRY_LONG"
    EXIT_LONG = "EXIT_LONG"
    HOLD = "HOLD"