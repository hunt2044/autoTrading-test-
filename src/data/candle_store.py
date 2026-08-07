import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import UTC
from decimal import Decimal
from pathlib import Path

import pandas as pd

from config.schema import get_settings
from src.core.enums import DataSource
from src.core.models import Candle


class CandleStore(ABC):
    @abstractmethod
    def append(self, candles: list[Candle]) -> int:
        pass

    @abstractmethod
    def get_latest(
        self, symbol: str, interval: str, source: DataSource, limit: int = 1
    ) -> list[Candle]:
        pass

    @abstractmethod
    def get_range(
        self, symbol: str, interval: str, source: DataSource, start_ts: int, end_ts: int
    ) -> list[Candle]:
        pass

    @abstractmethod
    def get_all(self, symbol: str, interval: str, source: DataSource) -> list[Candle]:
        pass

    @abstractmethod
    def count(self, symbol: str, interval: str, source: DataSource) -> int:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class ParquetStore(CandleStore):
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, symbol: str, interval: str, source: DataSource) -> Path:
        safe_symbol = symbol.replace("/", "_")
        return self.data_dir / f"{safe_symbol}_{interval}_{source.value}.parquet"

    def append(self, candles: list[Candle]) -> int:
        if not candles:
            return 0
        df = pd.DataFrame([c.to_dict() for c in candles])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        file_path = self._file_path(candles[0].symbol, candles[0].interval, candles[0].source)

        if file_path.exists():
            existing = pd.read_parquet(file_path)
            existing["timestamp"] = pd.to_datetime(existing["timestamp"])
            combined = pd.concat([existing, df]).drop_duplicates(
                subset=["timestamp"], keep="last"
            )
            combined = combined.sort_values("timestamp").reset_index(drop=True)
        else:
            combined = df.sort_values("timestamp").reset_index(drop=True)

        combined.to_parquet(file_path, index=False)
        return len(candles)

    def get_latest(
        self, symbol: str, interval: str, source: DataSource, limit: int = 1
    ) -> list[Candle]:
        file_path = self._file_path(symbol, interval, source)
        if not file_path.exists():
            return []
        df = pd.read_parquet(file_path)
        if df.empty:
            return []
        df = df.sort_values("timestamp").tail(limit)
        return [Candle.from_dict(row.to_dict()) for _, row in df.iterrows()]

    def get_range(
        self, symbol: str, interval: str, source: DataSource, start_ts: int, end_ts: int
    ) -> list[Candle]:
        file_path = self._file_path(symbol, interval, source)
        if not file_path.exists():
            return []
        df = pd.read_parquet(file_path)
        if df.empty:
            return []
        start_dt = pd.Timestamp(start_ts, unit="ms", tz="UTC")
        end_dt = pd.Timestamp(end_ts, unit="ms", tz="UTC")
        mask = (df["timestamp"] >= start_dt) & (df["timestamp"] <= end_dt)
        df = df[mask].sort_values("timestamp")
        return [Candle.from_dict(row.to_dict()) for _, row in df.iterrows()]

    def get_all(self, symbol: str, interval: str, source: DataSource) -> list[Candle]:
        file_path = self._file_path(symbol, interval, source)
        if not file_path.exists():
            return []
        df = pd.read_parquet(file_path)
        if df.empty:
            return []
        df = df.sort_values("timestamp")
        return [Candle.from_dict(row.to_dict()) for _, row in df.iterrows()]

    def count(self, symbol: str, interval: str, source: DataSource) -> int:
        file_path = self._file_path(symbol, interval, source)
        if not file_path.exists():
            return 0
        df = pd.read_parquet(file_path)
        return len(df)

    def close(self) -> None:
        pass


class CSVStore(CandleStore):
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, symbol: str, interval: str, source: DataSource) -> Path:
        safe_symbol = symbol.replace("/", "_")
        return self.data_dir / f"{safe_symbol}_{interval}_{source.value}.csv"

    def append(self, candles: list[Candle]) -> int:
        if not candles:
            return 0
        df = pd.DataFrame([c.to_dict() for c in candles])
        file_path = self._file_path(candles[0].symbol, candles[0].interval, candles[0].source)

        if file_path.exists():
            existing = pd.read_csv(file_path)
            existing["timestamp"] = pd.to_datetime(existing["timestamp"])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            combined = pd.concat([existing, df]).drop_duplicates(subset=["timestamp"], keep="last")
            combined = combined.sort_values("timestamp").reset_index(drop=True)
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            combined = df.sort_values("timestamp").reset_index(drop=True)

        combined.to_csv(file_path, index=False)
        return len(candles)

    def get_latest(
        self, symbol: str, interval: str, source: DataSource, limit: int = 1
    ) -> list[Candle]:
        file_path = self._file_path(symbol, interval, source)
        if not file_path.exists():
            return []
        df = pd.read_csv(file_path)
        if df.empty:
            return []
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").tail(limit)
        return [Candle.from_dict(row.to_dict()) for _, row in df.iterrows()]

    def get_range(
        self, symbol: str, interval: str, source: DataSource, start_ts: int, end_ts: int
    ) -> list[Candle]:
        file_path = self._file_path(symbol, interval, source)
        if not file_path.exists():
            return []
        df = pd.read_csv(file_path)
        if df.empty:
            return []
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        start_dt = pd.Timestamp(start_ts, unit="ms", tz="UTC")
        end_dt = pd.Timestamp(end_ts, unit="ms", tz="UTC")
        mask = (df["timestamp"] >= start_dt) & (df["timestamp"] <= end_dt)
        df = df[mask].sort_values("timestamp")
        return [Candle.from_dict(row.to_dict()) for _, row in df.iterrows()]

    def get_all(self, symbol: str, interval: str, source: DataSource) -> list[Candle]:
        file_path = self._file_path(symbol, interval, source)
        if not file_path.exists():
            return []
        df = pd.read_csv(file_path)
        if df.empty:
            return []
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
        return [Candle.from_dict(row.to_dict()) for _, row in df.iterrows()]

    def count(self, symbol: str, interval: str, source: DataSource) -> int:
        file_path = self._file_path(symbol, interval, source)
        if not file_path.exists():
            return 0
        df = pd.read_csv(file_path)
        return len(df)

    def close(self) -> None:
        pass


class SQLiteStore(CandleStore):
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "candles.db"
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    source TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open TEXT NOT NULL,
                    high TEXT NOT NULL,
                    low TEXT NOT NULL,
                    close TEXT NOT NULL,
                    volume TEXT NOT NULL,
                    quote_asset_volume TEXT,
                    number_of_trades INTEGER,
                    taker_buy_base_volume TEXT,
                    taker_buy_quote_volume TEXT,
                    PRIMARY KEY (symbol, interval, source, timestamp)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_candles_lookup
                ON candles (symbol, interval, source, timestamp)
            """)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def append(self, candles: list[Candle]) -> int:
        if not candles:
            return 0
        with self._conn() as conn:
            for c in candles:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO candles
                    (symbol, interval, source, timestamp, open, high, low, close, volume,
                     quote_asset_volume, number_of_trades, taker_buy_base_volume,
                     taker_buy_quote_volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c.symbol,
                        c.interval,
                        c.source.value,
                        int(c.timestamp.timestamp() * 1000),
                        str(c.open),
                        str(c.high),
                        str(c.low),
                        str(c.close),
                        str(c.volume),
                        str(c.quote_asset_volume),
                        c.number_of_trades,
                        str(c.taker_buy_base_volume),
                        str(c.taker_buy_quote_volume),
                    ),
                )
            conn.commit()
        return len(candles)

    def get_latest(
        self, symbol: str, interval: str, source: DataSource, limit: int = 1
    ) -> list[Candle]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM candles
                WHERE symbol=? AND interval=? AND source=?
                ORDER BY timestamp DESC LIMIT ?
                """,
                (symbol, interval, source.value, limit),
            ).fetchall()
        return [self._row_to_candle(r) for r in reversed(rows)]

    def get_range(
        self, symbol: str, interval: str, source: DataSource, start_ts: int, end_ts: int
    ) -> list[Candle]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM candles
                WHERE symbol=? AND interval=? AND source=? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
                """,
                (symbol, interval, source.value, start_ts, end_ts),
            ).fetchall()
        return [self._row_to_candle(r) for r in rows]

    def get_all(self, symbol: str, interval: str, source: DataSource) -> list[Candle]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM candles
                WHERE symbol=? AND interval=? AND source=?
                ORDER BY timestamp ASC
                """,
                (symbol, interval, source.value),
            ).fetchall()
        return [self._row_to_candle(r) for r in rows]

    def count(self, symbol: str, interval: str, source: DataSource) -> int:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM candles
                WHERE symbol=? AND interval=? AND source=?
                """,
                (symbol, interval, source.value),
            ).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        pass

    @staticmethod
    def _row_to_candle(row: sqlite3.Row) -> Candle:
        from datetime import datetime

        return Candle(
            symbol=row["symbol"],
            interval=row["interval"],
            timestamp=datetime.fromtimestamp(row["timestamp"] / 1000, tz=UTC),
            open=Decimal(row["open"]),
            high=Decimal(row["high"]),
            low=Decimal(row["low"]),
            close=Decimal(row["close"]),
            volume=Decimal(row["volume"]),
            source=DataSource(row["source"]),
            quote_asset_volume=Decimal(row["quote_asset_volume"] or "0"),
            number_of_trades=row["number_of_trades"] or 0,
            taker_buy_base_volume=Decimal(row["taker_buy_base_volume"] or "0"),
            taker_buy_quote_volume=Decimal(row["taker_buy_quote_volume"] or "0"),
        )


def create_store() -> CandleStore:
    settings = get_settings()
    data_dir = Path(settings.data_dir)
    fmt = settings.storage_format
    if fmt == "parquet":
        return ParquetStore(data_dir)
    elif fmt == "csv":
        return CSVStore(data_dir)
    elif fmt == "sqlite":
        return SQLiteStore(data_dir)
    else:
        raise ValueError(f"Unknown storage format: {fmt}")