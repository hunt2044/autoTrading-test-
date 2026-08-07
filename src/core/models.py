from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from src.core.enums import DataSource, OrderSide, OrderStatus, OrderType, PositionSide, SignalAction


@dataclass(slots=True)
class Candle:
    symbol: str
    interval: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: DataSource
    quote_asset_volume: Decimal = Decimal("0")
    number_of_trades: int = 0
    taker_buy_base_volume: Decimal = Decimal("0")
    taker_buy_quote_volume: Decimal = Decimal("0")

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "timestamp": self.timestamp.isoformat(),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": str(self.volume),
            "source": self.source.value,
            "quote_asset_volume": str(self.quote_asset_volume),
            "number_of_trades": self.number_of_trades,
            "taker_buy_base_volume": str(self.taker_buy_base_volume),
            "taker_buy_quote_volume": str(self.taker_buy_quote_volume),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Candle":
        return cls(
            symbol=data["symbol"],
            interval=data["interval"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            open=Decimal(data["open"]),
            high=Decimal(data["high"]),
            low=Decimal(data["low"]),
            close=Decimal(data["close"]),
            volume=Decimal(data["volume"]),
            source=DataSource(data["source"]),
            quote_asset_volume=Decimal(data.get("quote_asset_volume", "0")),
            number_of_trades=int(data.get("number_of_trades", 0)),
            taker_buy_base_volume=Decimal(data.get("taker_buy_base_volume", "0")),
            taker_buy_quote_volume=Decimal(data.get("taker_buy_quote_volume", "0")),
        )


@dataclass(slots=True)
class Indicators:
    ema_short: Decimal | None = None
    ema_long: Decimal | None = None
    atr: Decimal | None = None
    prev_ema_short: Decimal | None = None
    prev_ema_long: Decimal | None = None


@dataclass(slots=True)
class Signal:
    action: SignalAction
    price: Decimal
    timestamp: datetime
    indicators: Indicators
    strength: float = 1.0


@dataclass(slots=True)
class Order:
    id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Decimal | None = None
    commission: Decimal = Decimal("0")
    commission_asset: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    update_time: datetime | None = None


@dataclass(slots=True)
class Position:
    symbol: str
    side: PositionSide = PositionSide.FLAT
    quantity: Decimal = Decimal("0")
    entry_price: Decimal | None = None
    stop_loss: Decimal | None = None
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    entry_time: datetime | None = None
    last_update: datetime | None = None


@dataclass(slots=True)
class Account:
    total_equity: Decimal
    available_balance: Decimal
    positions: dict[str, Position] = field(default_factory=dict)
    last_update: datetime = field(default_factory=datetime.utcnow)

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]


@dataclass(slots=True)
class Trade:
    symbol: str
    side: OrderSide
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    entry_time: datetime
    exit_time: datetime
    pnl: Decimal
    commission: Decimal
    stop_loss: Decimal
    atr_at_entry: Decimal