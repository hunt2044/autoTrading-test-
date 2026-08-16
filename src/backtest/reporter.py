
from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class BacktestReporter:
    @staticmethod
    def print_summary(result: dict) -> None:
        metrics = result["metrics"]
        logger.info("=" * 50)
        logger.info("BACKTEST RESULTS")
        logger.info("=" * 50)
        logger.info(f"Initial Capital:  {result.get('initial_capital', 0):,.2f} USDT")
        logger.info(f"Final Equity:     {result['final_equity']:,.2f} USDT")
        logger.info(f"Total Return:     {result['total_return'] * 100:.2f}%")
        if result.get("halted_due_to_insolvency"):
            logger.warning("BACKTEST HALTED: Account became insolvent (equity <= 0) before completing all candles")
        logger.info("-" * 50)
        logger.info(f"Total Trades:     {metrics['total_trades']}")
        logger.info(f"Win Rate:         {metrics['win_rate'] * 100:.2f}%")
        logger.info(f"Avg Win:          {metrics['avg_win']:,.2f} USDT")
        logger.info(f"Avg Loss:         {metrics['avg_loss']:,.2f} USDT")
        logger.info(f"Profit Factor:    {metrics['profit_factor']:.2f}")
        logger.info(f"Max Drawdown:     {metrics['max_drawdown'] * 100:.2f}%")
        logger.info(f"Sharpe Ratio:     {metrics['sharpe_ratio']:.2f}")
        logger.info(f"Max Position Size: {metrics['max_position_size_ratio'] * 100:.2f}% of equity")
        logger.info("=" * 50)

    @staticmethod
    def save_trades_csv(result: dict, filepath: str) -> None:
        import csv

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "symbol", "side", "quantity", "entry_price", "exit_price",
                "entry_time", "exit_time", "pnl", "commission", "stop_loss", "atr_at_entry"
            ])
            for t in result["trades"]:
                writer.writerow([
                    t.symbol, t.side.value, str(t.quantity), str(t.entry_price),
                    str(t.exit_price), t.entry_time.isoformat(), t.exit_time.isoformat(),
                    str(t.pnl), str(t.commission), str(t.stop_loss), str(t.atr_at_entry)
                ])

    @staticmethod
    def save_equity_curve_csv(result: dict, filepath: str) -> None:
        import csv
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "equity"])
            for ts, equity in result["equity_curve"]:
                writer.writerow([ts.isoformat(), str(equity)])