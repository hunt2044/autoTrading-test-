from abc import ABC, abstractmethod
from typing import Any

from src.core.enums import DataSource
from src.core.models import Candle


class DataProvider(ABC):
    @abstractmethod
    def fetch_historical(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        limit: int = 1000,
    ) -> list[Candle]:
        pass

    @abstractmethod
    def fetch_latest(self, symbol: str, interval: str, limit: int = 2) -> list[Candle]:
        pass

    @abstractmethod
    def get_source(self) -> DataSource:
        pass


class BacktestDataProvider(DataProvider):
    def __init__(self, client: Any, store: Any):
        self.client = client
        self.store = store

    def fetch_historical(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        limit: int = 1000,
    ) -> list[Candle]:
        all_candles = []
        current_start = start_time

        while current_start < end_time:
            candles = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=end_time,
                limit=limit,
            )
            if not candles:
                break

            all_candles.extend(candles)
            current_start = int(candles[-1].timestamp.timestamp() * 1000) + 1

            if len(candles) < limit:
                break

        if all_candles:
            self.store.append(all_candles)

        return all_candles

    def fetch_latest(self, symbol: str, interval: str, limit: int = 2) -> list[Candle]:
        return self.store.get_latest(symbol, interval, DataSource.BACKTEST, limit)

    def get_source(self) -> DataSource:
        return DataSource.BACKTEST


class LiveDataProvider(DataProvider):
    def __init__(self, client: Any, store: Any):
        self.client = client
        self.store = store

    def fetch_historical(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        limit: int = 1000,
    ) -> list[Candle]:
        all_candles = []
        current_start = start_time

        while current_start < end_time:
            candles = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=end_time,
                limit=limit,
            )
            if not candles:
                break

            all_candles.extend(candles)
            current_start = int(candles[-1].timestamp.timestamp() * 1000) + 1

            if len(candles) < limit:
                break

        if all_candles:
            for c in all_candles:
                c.source = DataSource.LIVE
            self.store.append(all_candles)

        return all_candles

    def fetch_latest(self, symbol: str, interval: str, limit: int = 2) -> list[Candle]:
        candles = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
        for c in candles:
            c.source = DataSource.LIVE
        if candles:
            self.store.append(candles)
        return candles

    def get_source(self) -> DataSource:
        return DataSource.LIVE


def create_data_provider(mode: str, client: Any, store: Any) -> DataProvider:
    if mode == "backtest":
        return BacktestDataProvider(client, store)
    elif mode == "live":
        return LiveDataProvider(client, store)
    else:
        raise ValueError(f"Unknown mode: {mode}")