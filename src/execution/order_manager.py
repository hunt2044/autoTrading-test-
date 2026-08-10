from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from src.core.enums import OrderSide, OrderStatus, OrderType
from src.core.models import Order
from src.data.binance_client import BinanceClient, unwrap_error


@dataclass(slots=True)
class OrderResult:
    order: Order
    success: bool
    error: str | None = None


class OrderManager:
    def __init__(self, client: BinanceClient):
        self.client = client
        self.pending_orders: dict[str, Order] = {}

    def place_market_buy(self, symbol: str, quantity: Decimal) -> OrderResult:
        return self._place_order(symbol, OrderSide.BUY, OrderType.MARKET, quantity)

    def place_market_sell(self, symbol: str, quantity: Decimal) -> OrderResult:
        return self._place_order(symbol, OrderSide.SELL, OrderType.MARKET, quantity)

    def _place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> OrderResult:
        client_order_id = f"mvp_{uuid4().hex[:16]}"
        try:
            order = self.client.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
            )
            order.client_order_id = client_order_id
            self.pending_orders[order.id] = order
            return OrderResult(order=order, success=True)
        except Exception as e:
            return OrderResult(
                order=Order(
                    id="",
                    client_order_id=client_order_id,
                    symbol=symbol,
                    side=side,
                    type=order_type,
                    quantity=quantity,
                    price=price,
                    status=OrderStatus.REJECTED,
                ),
                success=False,
                error=unwrap_error(e),
            )

    def get_order_status(self, order_id: str) -> Order | None:
        if order_id in self.pending_orders:
            order = self.pending_orders[order_id]
            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED):
                return order
            try:
                updated = self.client.get_order(order.symbol, int(order.id))
                self.pending_orders[order_id] = updated
                return updated
            except Exception:
                return order
        return None

    def cancel_order(self, order_id: str) -> OrderResult:
        if order_id not in self.pending_orders:
            return OrderResult(
                order=Order(
                    id=order_id,
                    client_order_id="",
                    symbol="",
                    side=OrderSide.BUY,
                    type=OrderType.MARKET,
                    quantity=Decimal("0"),
                    status=OrderStatus.REJECTED,
                ),
                success=False,
                error="Order not found locally",
            )

        order = self.pending_orders[order_id]
        try:
            cancelled = self.client.cancel_order(order.symbol, int(order.id))
            self.pending_orders[order_id] = cancelled
            return OrderResult(order=cancelled, success=True)
        except Exception as e:
            return OrderResult(order=order, success=False, error=unwrap_error(e))

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        try:
            return self.client.get_open_orders(symbol)
        except Exception:
            return []

    def cleanup_filled_orders(self) -> None:
        filled_ids = [
            oid for oid, order in self.pending_orders.items()
            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED)
        ]
        for oid in filled_ids:
            del self.pending_orders[oid]