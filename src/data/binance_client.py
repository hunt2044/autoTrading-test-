import hashlib
import hmac
import time
from datetime import UTC
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    RetryError,
)


def unwrap_error(e: Exception) -> str:
    """Return the real underlying error message, unwrapping tenacity's RetryError
    if present, so callers see the actual BinanceAPIError instead of the opaque
    RetryError wrapper."""
    if isinstance(e, RetryError):
        try:
            inner = e.last_attempt.exception()
            if inner is not None:
                return str(inner)
        except Exception:
            pass
    return str(e)


from config.schema import BinanceConfig, get_settings
from src.core.enums import DataSource, OrderSide, OrderStatus, OrderType
from src.core.models import Candle, Order


class BinanceAPIError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Binance API Error {code}: {message}")


class BinanceClient:
    def __init__(self, config: BinanceConfig, base_url: str):
        self.config = config
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=30.0)
        self._last_request_time = 0.0
        self._min_request_interval = 0.05

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.monotonic()

    def _sign_params(self, params: dict[str, Any]) -> str:
        query_string = urlencode(params, doseq=True)
        signature = hmac.new(
            self.config.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    def _get_headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": self.config.api_key}

    @retry(
        wait=wait_exponential_jitter(initial=1, max=30),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(
            (httpx.RequestError, httpx.TimeoutException, BinanceAPIError)
        ),
    )
    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        self._rate_limit()
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers() if signed else {}

        request_params = params or {}
        if signed:
            request_params["timestamp"] = int(time.time() * 1000)
            request_params["recvWindow"] = self.config.recv_window
            query_string = self._sign_params(request_params)
            url = f"{url}?{query_string}"
            request_params = None

        response = self._client.request(method, url, params=request_params, headers=headers)

        if response.status_code == 429:
            raise BinanceAPIError(429, "Rate limit exceeded")

        if response.status_code >= 400:
            try:
                error_data = response.json()
                raise BinanceAPIError(
                    response.status_code, error_data.get("msg", response.text)
                ) from None
            except Exception as exc:
                raise BinanceAPIError(response.status_code, response.text) from exc

        data = response.json()
        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            raise BinanceAPIError(data["code"], data.get("msg", str(data)))
        return data

    def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 1000,
    ) -> list[Candle]:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        data = self._request("GET", "/v3/klines", params)
        return [self._parse_kline(k, symbol, interval, DataSource.BACKTEST) for k in data]

    def _parse_kline(self, k: list, symbol: str, interval: str, source: DataSource) -> Candle:
        return Candle(
            symbol=symbol,
            interval=interval,
            timestamp=self._ms_to_datetime(k[0]),
            open=Decimal(str(k[1])),
            high=Decimal(str(k[2])),
            low=Decimal(str(k[3])),
            close=Decimal(str(k[4])),
            volume=Decimal(str(k[5])),
            source=source,
            quote_asset_volume=Decimal(str(k[7])),
            number_of_trades=int(k[8]),
            taker_buy_base_volume=Decimal(str(k[9])),
            taker_buy_quote_volume=Decimal(str(k[10])),
        )

    @staticmethod
    def _ms_to_datetime(ms: int) -> time:
        from datetime import datetime
        return datetime.fromtimestamp(ms / 1000, tz=UTC)

    def get_account(self) -> dict:
        return self._request("GET", "/v3/account", signed=True)

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        params = {}
        if symbol:
            params["symbol"] = symbol
        data = self._request("GET", "/v3/openOrders", params, signed=True)
        return [self._parse_order(o) for o in data]

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> Order:
        params = {
            "symbol": symbol,
            "side": side.value,
            "type": order_type.value,
            "quantity": self._format_quantity(quantity),
        }
        if price and order_type == OrderType.LIMIT:
            params["price"] = self._format_price(price)
            params["timeInForce"] = "GTC"

        data = self._request("POST", "/v3/order", params, signed=True)
        return self._parse_order(data)

    def cancel_order(self, symbol: str, order_id: int) -> Order:
        params = {"symbol": symbol, "orderId": order_id}
        data = self._request("DELETE", "/v3/order", params, signed=True)
        return self._parse_order(data)

    def get_order(self, symbol: str, order_id: int) -> Order:
        params = {"symbol": symbol, "orderId": order_id}
        data = self._request("GET", "/v3/order", params, signed=True)
        return self._parse_order(data)

    def _parse_order(self, data: dict) -> Order:
        from datetime import datetime

        return Order(
            id=str(data["orderId"]),
            client_order_id=data["clientOrderId"],
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            type=OrderType(data["type"]),
            quantity=Decimal(str(data["origQty"])),
            price=Decimal(str(data["price"])) if data["price"] != "0.00000000" else None,
            status=OrderStatus(data["status"]),
            filled_quantity=Decimal(str(data["executedQty"])),
            avg_fill_price=(
                Decimal(str(data["avgPrice"]))
                if data["avgPrice"] != "0.00000000"
                else None
            ),
            commission=Decimal("0"),
            commission_asset="",
            timestamp=datetime.fromtimestamp(data["time"] / 1000, tz=UTC),
            update_time=datetime.fromtimestamp(data["updateTime"] / 1000, tz=UTC)
            if data.get("updateTime")
            else None,
        )

    @staticmethod
    def _format_quantity(qty: Decimal) -> str:
        return f"{qty:f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_price(price: Decimal) -> str:
        return f"{price:f}".rstrip("0").rstrip(".")

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_mainnet_client() -> BinanceClient:
    settings = get_settings()
    return BinanceClient(settings.binance, settings.binance.mainnet_base_url)


def create_demo_client() -> BinanceClient:
    settings = get_settings()
    return BinanceClient(settings.binance, settings.binance.demo_base_url)