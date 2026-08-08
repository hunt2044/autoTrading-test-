import time
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Event

from config.schema import get_settings
from src.core.enums import PositionSide, SignalAction
from src.core.models import Account, Candle, Indicators, Position, Signal
from src.data import (
    BinanceClient,
    CandleStore,
    DataProvider,
    DataSource,
    create_data_provider,
    create_demo_client,
    create_store,
)
from src.execution import OrderManager, OrderResult, Reconciler
from src.indicators import IndicatorCalculator
from src.monitoring.logger import get_logger
from src.risk import RiskManager
from src.signal import EmaCrossoverSignal

logger = get_logger(__name__)


class LiveRunner:
    WARMUP_CANDLES = 60

    def __init__(self):
        self.settings = get_settings()
        self._stop_event = Event()
        self._initialized = False

        self.client: BinanceClient | None = None
        self.store: CandleStore | None = None
        self.provider: DataProvider | None = None
        self.order_manager: OrderManager | None = None
        self.reconciler: Reconciler | None = None

        self.account: Account | None = None
        self.position: Position | None = None
        self.indicators: IndicatorCalculator | None = None
        self.signal_gen: EmaCrossoverSignal | None = None
        self.risk_manager: RiskManager | None = None

        self.last_candle_time: datetime | None = None
        self.missed_candle_count = 0

    def initialize(self) -> None:
        if self._initialized:
            return

        self.client = create_demo_client()
        self.store = create_store()
        self.provider = create_data_provider("live", self.client, self.store)
        self.order_manager = OrderManager(self.client)
        self.reconciler = Reconciler(
            self.client, Decimal(str(self.settings.live.reconciliation_tolerance))
        )

        self.account = Account(
            total_equity=Decimal(str(self.settings.initial_capital)),
            available_balance=Decimal(str(self.settings.initial_capital)),
        )
        self.position = Position(symbol=self.settings.symbol)
        self.account.positions[self.settings.symbol] = self.position

        self.indicators = IndicatorCalculator()
        self.signal_gen = EmaCrossoverSignal()
        self.risk_manager = RiskManager()

        self._warmup_indicators()

        self._initialized = True

    def _warmup_indicators(self) -> None:
        logger.info("Warming up indicators with {} historical candles...", self.WARMUP_CANDLES)
        try:
            end_time = int(datetime.now(UTC).timestamp() * 1000)
            start_time = end_time - (self.WARMUP_CANDLES * 4 * 60 * 60 * 1000)
            
            candles = self.provider.fetch_historical(
                self.settings.symbol,
                self.settings.interval,
                start_time=start_time,
                end_time=end_time,
                limit=1000,
            )
            
            if not candles:
                logger.warning("No historical candles fetched for warm-up")
                return
            
            candles.sort(key=lambda c: c.timestamp)
            
            last_indicators: Indicators | None = None
            for candle in candles:
                last_indicators = self.indicators.process_candle(candle)
            
            self.last_candle_time = candles[-1].timestamp
            
            if last_indicators:
                logger.info(
                    "Warmed up indicators with {} candles: EMA20={:.2f}, EMA50={:.2f}, ATR={:.2f}",
                    len(candles),
                    last_indicators.ema_short,
                    last_indicators.ema_long,
                    last_indicators.atr,
                )
            else:
                logger.info("Warmed up indicators with {} candles", len(candles))
                
        except Exception as e:
            logger.warning("Indicator warm-up failed: {}", e)

    def run(self) -> None:
        self.initialize()

        logger.info("Starting live paper trading...")
        logger.info("Symbol: {}", self.settings.symbol)
        logger.info("Interval: {}", self.settings.interval)
        logger.info("Initial Capital: {} USDT", self.settings.initial_capital)

        self._sync_initial_state()

        while not self._stop_event.is_set():
            try:
                self._run_iteration()
            except KeyboardInterrupt:
                logger.info("Shutdown signal received")
                break
            except Exception as e:
                logger.error("Error in main loop: {}", e)
                time.sleep(60)

        self.shutdown()

    def _sync_initial_state(self) -> None:
        logger.info("Syncing initial state with Demo Mode...")
        try:
            self.account = self.reconciler.sync_account(self.account)
            self.position = self.account.get_position(self.settings.symbol)
            logger.info(
                "Synced - Balance: {}, Position: {} {}",
                self.account.available_balance,
                self.position.side,
                self.position.quantity,
            )
        except Exception as e:
            logger.warning("Failed to sync initial state: {}", e)

    def _run_iteration(self) -> None:
        next_candle_close = self._get_next_candle_close()
        now = datetime.now(UTC)

        sleep_seconds = (next_candle_close - now).total_seconds()
        if sleep_seconds > 0:
            logger.info(
                "Next candle closes at {}, sleeping {:.0f}s",
                next_candle_close.isoformat(),
                sleep_seconds,
            )
            time.sleep(min(sleep_seconds, 3600))
            if self._stop_event.is_set():
                return

        candles = self.provider.fetch_latest(
            self.settings.symbol, self.settings.interval, limit=2
        )
        if not candles:
            self.missed_candle_count += 1
            if (
                self.missed_candle_count
                >= self.settings.live.alert_missing_candle_hours / 4
            ):
                logger.warning(
                    "ALERT: No new candle received for {} hours",
                    self.missed_candle_count * 4,
                )
            return

        self.missed_candle_count = 0
        closed_candle = candles[-2] if len(candles) >= 2 else candles[-1]

        if self.last_candle_time and closed_candle.timestamp <= self.last_candle_time:
            logger.debug("Candle {} already processed, skipping", closed_candle.timestamp)
            return

        self.last_candle_time = closed_candle.timestamp
        self._process_candle(closed_candle)

        self.order_manager.cleanup_filled_orders()

    def _get_next_candle_close(self) -> datetime:
        now = datetime.now(UTC)
        current_hour = now.hour
        next_4h = ((current_hour // 4) + 1) * 4
        if next_4h >= 24:
            next_4h = 0
            next_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            next_day += timedelta(days=1)
            return next_day
        return now.replace(hour=next_4h, minute=0, second=0, microsecond=0)

    def _process_candle(self, candle: Candle) -> None:
        logger.info(
            "Processing candle: {} O:{} H:{} L:{} C:{}",
            candle.timestamp,
            candle.open,
            candle.high,
            candle.low,
            candle.close,
        )

        indicators = self.indicators.process_candle(candle)
        signal = self.signal_gen.generate(candle, indicators, self.position.side)

        is_stop_triggered = (
            self.position.side == PositionSide.LONG
            and self.position.stop_loss
            and candle.low <= self.position.stop_loss
        )
        if is_stop_triggered:
            logger.warning("STOP LOSS TRIGGERED at {}", self.position.stop_loss)
            self._execute_exit(self.position.stop_loss, candle.timestamp, "STOP_LOSS")
            return

        if signal and signal.action != SignalAction.HOLD:
            logger.info("Signal: {} at {}", signal.action.value, signal.price)
            if signal.action == SignalAction.ENTRY_LONG:
                self._execute_entry(signal, candle)
            elif signal.action == SignalAction.EXIT_LONG:
                self._execute_exit(signal.price, candle.timestamp, "SIGNAL")

        self._log_status(candle, indicators)

    def _execute_entry(self, signal: Signal, candle: Candle) -> None:
        if self.position.side != PositionSide.FLAT:
            logger.warning("Already in position, skipping entry")
            return

        try:
            risk_params = self.risk_manager.calculate_position_size(
                self.account.total_equity,
                signal.price,
                signal.indicators,
            )
        except ValueError as e:
            logger.error("Risk calculation failed: {}", e)
            return

        logger.info(
            "Placing BUY order: qty={}, stop={}",
            risk_params.quantity,
            risk_params.stop_loss,
        )

        result: OrderResult = self.order_manager.place_market_buy(
            self.settings.symbol, risk_params.quantity
        )

        if result.success:
            self.position.side = PositionSide.LONG
            self.position.quantity = risk_params.quantity
            self.position.entry_price = signal.price
            self.position.stop_loss = risk_params.stop_loss
            self.position.entry_time = candle.timestamp
            self.account.available_balance -= risk_params.quantity * signal.price
            logger.info("Order placed: {}, status: {}", result.order.id, result.order.status)
        else:
            logger.error("Order failed: {}", result.error)

    def _execute_exit(self, exit_price: Decimal, exit_time: datetime, reason: str) -> None:
        if self.position.side != PositionSide.LONG or self.position.quantity == 0:
            logger.warning("No position to exit")
            return

        logger.info("Placing SELL order: qty={}, reason={}", self.position.quantity, reason)

        result: OrderResult = self.order_manager.place_market_sell(
            self.settings.symbol, self.position.quantity
        )

        if result.success:
            entry = self.position.entry_price or Decimal("0")
            pnl = (exit_price - entry) * self.position.quantity
            logger.info("Position closed: PnL={}", pnl)
            self.position.side = PositionSide.FLAT
            self.position.quantity = Decimal("0")
            self.position.entry_price = None
            self.position.stop_loss = None
            self.position.entry_time = None
            self.account.available_balance += self.position.quantity * exit_price
        else:
            logger.error("Exit order failed: {}", result.error)

    def _log_status(self, candle: Candle, indicators: Indicators) -> None:
        equity = self.account.total_equity
        if self.position.side == PositionSide.LONG and self.position.quantity > 0:
            unrealized = (
                candle.close - (self.position.entry_price or Decimal("0"))
            ) * self.position.quantity
            equity += unrealized

        logger.info(
            "Equity: {:.2f} | Position: {} {} | EMA20: {} | EMA50: {} | ATR: {}",
            equity,
            self.position.side,
            self.position.quantity,
            indicators.ema_short,
            indicators.ema_long,
            indicators.atr,
        )

    def shutdown(self) -> None:
        logger.info("Shutting down...")
        self._stop_event.set()

        if self.order_manager:
            open_orders = self.order_manager.get_open_orders(self.settings.symbol)
            for order in open_orders:
                logger.info("Cancelling open order: {}", order.id)
                with suppress(Exception):
                    self.order_manager.cancel_order(order.id)

        if self.client:
            self.client.close()

        logger.info("Shutdown complete")

    def stop(self) -> None:
        self._stop_event.set()