import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from config.schema import get_settings, load_settings_from_yaml, reload_settings
from src.backtest import BacktestEngine, BacktestReporter
from src.data import create_mainnet_client, create_store
from src.live import LiveRunner

app = typer.Typer(
    name="eth-4h-mvp",
    help="ETH 4H MVP Trading System - Paper Trading on Binance Demo Mode",
    add_completion=False,
)
console = Console()


@app.command()
def backtest(
    config: Path = typer.Option(Path("config/settings.yaml"), "--config", "-c", help="Config file path"),
    start: str = typer.Option("", "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option("", "--end", "-e", help="End date (YYYY-MM-DD)"),
    years: int = typer.Option(3, "--years", "-y", help="Years of history to fetch"),
    output: Path = typer.Option(Path("./results"), "--output", "-o", help="Output directory"),
) -> None:
    settings = reload_settings()
    if config.exists():
        settings = load_settings_from_yaml(str(config))

    console.print(f"[bold]Starting backtest[/bold] for {settings.symbol} {settings.interval}")
    console.print(f"Initial capital: {settings.initial_capital} USDT")

    output.mkdir(parents=True, exist_ok=True)

    client = create_mainnet_client()
    store = create_store()

    try:
        if end:
            end_dt = datetime.fromisoformat(end).replace(tzinfo=UTC)
            end_ts = int(end_dt.timestamp() * 1000)
        else:
            end_ts = int(datetime.now(UTC).timestamp() * 1000)

        if start:
            start_dt = datetime.fromisoformat(start).replace(tzinfo=UTC)
            start_ts = int(start_dt.timestamp() * 1000)
        else:
            start_ts = end_ts - years * 365 * 24 * 60 * 60 * 1000

        console.print(
            f"Fetching data from {datetime.fromtimestamp(start_ts/1000, tz=UTC)} "
            f"to {datetime.fromtimestamp(end_ts/1000, tz=UTC)}"
        )

        candles = []
        current_start = start_ts
        limit = 1000

        with console.status("[bold green]Fetching historical data...") as status:
            while current_start < end_ts:
                batch = client.get_klines(
                    symbol=settings.symbol,
                    interval=settings.interval,
                    start_time=current_start,
                    end_time=end_ts,
                    limit=limit,
                )
                if not batch:
                    break
                candles.extend(batch)
                current_start = int(batch[-1].timestamp.timestamp() * 1000) + 1
                status.update(f"Fetched {len(candles)} candles...")
                if len(batch) < limit:
                    break

        console.print(f"Total candles fetched: {len(candles)}")
        store.append(candles)

        engine = BacktestEngine(
            symbol=settings.symbol,
            initial_capital=Decimal(str(settings.initial_capital)),
            fee_rate=Decimal(str(settings.backtest.fee_rate)),
            slippage_bps=settings.backtest.slippage_bps,
        )

        with console.status("[bold green]Running backtest..."):
            result = engine.run(candles)

        BacktestReporter.print_summary(result)

        trades_file = output / "trades.csv"
        equity_file = output / "equity_curve.csv"
        BacktestReporter.save_trades_csv(result, str(trades_file))
        BacktestReporter.save_equity_curve_csv(result, str(equity_file))

        console.print(f"\nResults saved to {output}/")
        console.print(f"  - {trades_file}")
        console.print(f"  - {equity_file}")

    finally:
        client.close()


@app.command()
def live(
    config: Path = typer.Option(Path("config/settings.yaml"), "--config", "-c", help="Config file path"),
) -> None:
    if config.exists():
        reload_settings()

    runner = LiveRunner()
    try:
        runner.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    finally:
        runner.shutdown()


@app.command()
def fetch_history(
    config: Path = typer.Option(Path("config/settings.yaml"), "--config", "-c", help="Config file path"),
    years: int = typer.Option(3, "--years", "-y", help="Years of history to fetch"),
) -> None:
    settings = reload_settings()
    if config.exists():
        settings = load_settings_from_yaml(str(config))

    client = create_mainnet_client()
    store = create_store()

    try:
        end_ts = int(datetime.now(UTC).timestamp() * 1000)
        start_ts = end_ts - years * 365 * 24 * 60 * 60 * 1000

        console.print(
            f"Fetching {years} years of history for {settings.symbol} "
            f"{settings.interval}"
        )

        candles = []
        current_start = start_ts
        limit = 1000

        with console.status("[bold green]Fetching...") as status:
            while current_start < end_ts:
                batch = client.get_klines(
                    symbol=settings.symbol,
                    interval=settings.interval,
                    start_time=current_start,
                    end_time=end_ts,
                    limit=limit,
                )
                if not batch:
                    break
                candles.extend(batch)
                current_start = int(batch[-1].timestamp.timestamp() * 1000) + 1
                status.update(f"Fetched {len(candles)} candles...")
                if len(batch) < limit:
                    break

        console.print(f"Total candles: {len(candles)}")
        stored = store.append(candles)
        console.print(f"Stored {stored} new candles")

    finally:
        client.close()


@app.command()
def validate_config(
    config: Path = typer.Option(Path("config/settings.yaml"), "--config", "-c", help="Config file path"),
) -> None:
    try:
        settings = (
            load_settings_from_yaml(str(config)) if config.exists() else get_settings()
        )
        console.print("[green]Configuration is valid[/green]")

        table = Table(title="Current Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")

        for field_name, _field_info in settings.model_fields.items():
            value = getattr(settings, field_name)
            if hasattr(value, "model_dump"):
                value = value.model_dump()
            table.add_row(field_name, str(value))

        console.print(table)

    except Exception as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)


@app.command()
def show_config(
    config: Path = typer.Option(Path("config/settings.yaml"), "--config", "-c", help="Config file path"),
) -> None:
    settings = get_settings()
    if config.exists():
        settings = load_settings_from_yaml(str(config))

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    for field_name in settings.model_fields:
        value = getattr(settings, field_name)
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        table.add_row(field_name, str(value))

    console.print(table)


if __name__ == "__main__":
    app()