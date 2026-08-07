from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pandas as pd

from config.schema import get_settings
from src.core.enums import OrderSide, PositionSide, SignalAction
from src.core.models import Account, Candle, Order, Position, Signal, Trade
from src.indicators import IndicatorCalculator
from src.risk import RiskManager
from src.signal import EmaCrossoverSignal


@dataclass(slots=True)
class BacktestState:
    account: Account
    position: Position
    indicators: IndicatorCalculator
    signal_gen: EmaCrossoverSignal
    risk_manager: RiskManager
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple] = field(default_factory=list)
    current_order: Order | None = None
    pending_stop_loss: Decimal | None = None


class BacktestEngine:
    def __init__(
        self,
        symbol: str,
        initial_capital: Decimal,
        fee_rate: Decimal,
        slippage_bps: int,
    ):
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage = Decimal(slippage_bps) / Decimal(10000)
        self.settings = get_settings()

        self.state = BacktestState(
            account=Account(total_equity=initial_capital, available_balance=initial_capital),
            position=Position(symbol=symbol),
            indicators=IndicatorCalculator(),
            signal_gen=EmaCrossoverSignal(),
            risk_manager=RiskManager(),
        )
        self.state.account.positions[symbol] = self.state.position

    def run(self, candles: list[Candle]) -> dict[str, Any]:
        if not candles:
            return self._empty_result()

        for i, candle in enumerate(candles):
            self._process_candle(candle, i, candles)

        self._finalize()

        return {
            "trades": self.state.trades,
            "equity_curve": self.state.equity_curve,
            "final_equity": self.state.account.total_equity,
            "initial_capital": self.initial_capital,
            "total_return": (
                self.state.account.total_equity - self.initial_capital
            )
            / self.initial_capital,
            "metrics": self._calculate_metrics(),
        }

    def _process_candle(self, candle: Candle, idx: int, all_candles: list[Candle]) -> None:
        indicators = self.state.indicators.process_candle(candle)
        signal = self.state.signal_gen.generate(candle, indicators, self.state.position.side)

        if self.state.current_order:
            self._check_stop_loss(candle)

        if signal and signal.action != SignalAction.HOLD:
            self._execute_signal(signal, candle, idx, all_candles)

        self._update_equity(candle)

    def _execute_signal(
        self,
        signal: Signal,
        candle: Candle,
        idx: int,
        all_candles: list[Candle],
    ) -> None:
        if (
            signal.action == SignalAction.ENTRY_LONG
            and self.state.position.side == PositionSide.FLAT
        ):
            if idx + 1 >= len(all_candles):
                return
            next_candle = all_candles[idx + 1]
            entry_price = next_candle.open * (Decimal(1) + self.slippage)

            try:
                risk_params = self.state.risk_manager.calculate_position_size(
                    self.state.account.total_equity,
                    entry_price,
                    signal.indicators,
                )
            except ValueError:
                return

            self.state.position.side = PositionSide.LONG
            self.state.position.quantity = risk_params.quantity
            self.state.position.entry_price = entry_price
            self.state.position.stop_loss = risk_params.stop_loss
            self.state.position.entry_time = next_candle.timestamp
            self.state.pending_stop_loss = risk_params.stop_loss

            position_value = risk_params.quantity * entry_price
            commission = position_value * self.fee_rate
            self.state.account.available_balance -= position_value + commission

        elif (
            signal.action == SignalAction.EXIT_LONG
            and self.state.position.side == PositionSide.LONG
        ):
            if idx + 1 >= len(all_candles):
                return
            next_candle = all_candles[idx + 1]
            exit_price = next_candle.open * (Decimal(1) - self.slippage)

            self._close_position(exit_price, next_candle.timestamp, signal.indicators.atr)

    def _check_stop_loss(self, candle: Candle) -> None:
        if self.state.pending_stop_loss and candle.low <= self.state.pending_stop_loss:
            exit_price = self.state.pending_stop_loss
            self._close_position(exit_price, candle.timestamp, self.state.position.stop_loss)

    def _close_position(
        self,
        exit_price: Decimal,
        exit_time: Any,
        atr_at_entry: Decimal | None,
    ) -> None:
        if self.state.position.side != PositionSide.LONG or self.state.position.quantity == 0:
            return

        entry_price = self.state.position.entry_price or Decimal("0")
        pnl = (exit_price - entry_price) * self.state.position.quantity
        commission = self.state.position.quantity * exit_price * self.fee_rate
        net_pnl = pnl - commission

        trade = Trade(
            symbol=self.symbol,
            side=OrderSide.BUY,
            quantity=self.state.position.quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=self.state.position.entry_time or exit_time,
            exit_time=exit_time,
            pnl=net_pnl,
            commission=commission,
            stop_loss=self.state.position.stop_loss or Decimal("0"),
            atr_at_entry=atr_at_entry or Decimal("0"),
        )

        self.state.trades.append(trade)
        self.state.account.available_balance += (
            self.state.position.quantity * exit_price - commission
        )
        self.state.account.total_equity = self.state.account.available_balance

        self.state.position.side = PositionSide.FLAT
        self.state.position.quantity = Decimal("0")
        self.state.position.entry_price = None
        self.state.position.stop_loss = None
        self.state.position.entry_time = None
        self.state.pending_stop_loss = None

    def _update_equity(self, candle: Candle) -> None:
        if self.state.position.side == PositionSide.LONG and self.state.position.quantity > 0:
            unrealized = (
            candle.close - (self.state.position.entry_price or Decimal("0"))
        ) * self.state.position.quantity
            equity = self.state.account.available_balance + unrealized
        else:
            equity = self.state.account.available_balance

        self.state.account.total_equity = equity
        self.state.equity_curve.append((candle.timestamp, equity))

    def _finalize(self) -> None:
        if self.state.position.side == PositionSide.LONG and self.state.position.quantity > 0:
            last_price = self.state.position.entry_price or Decimal("0")
            self._close_position(
            last_price, self.state.position.entry_time, self.state.position.stop_loss
        )

    def _calculate_metrics(self) -> dict[str, float]:
        if not self.state.trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
            }

        equity_values = [float(e) for _, e in self.state.equity_curve]
        equity_series = pd.Series(equity_values)
        returns = equity_series.pct_change().dropna()

        wins = [float(t.pnl) for t in self.state.trades if t.pnl > 0]
        losses = [float(t.pnl) for t in self.state.trades if t.pnl <= 0]

        peak = equity_series.expanding().max()
        drawdown = (equity_series - peak) / peak
        max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0

        sharpe = 0.0
        if len(returns) > 1 and returns.std() > 0:
            sharpe = float(returns.mean() / returns.std() * (252**0.5))

        return {
            "total_trades": len(self.state.trades),
            "win_rate": len(wins) / len(self.state.trades) if self.state.trades else 0.0,
            "avg_win": sum(wins) / len(wins) if wins else 0.0,
            "avg_loss": sum(losses) / len(losses) if losses else 0.0,
            "profit_factor": (
                abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0.0
            ),
            "max_drawdown": float(max_dd),
            "sharpe_ratio": sharpe,
        }

    def _empty_result(self) -> dict[str, Any]:
        return {
            "trades": [],
            "equity_curve": [],
            "final_equity": self.initial_capital,
            "total_return": 0.0,
            "metrics": self._calculate_metrics(),
        }