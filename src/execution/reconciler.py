from dataclasses import dataclass
from decimal import Decimal

from src.core.models import Account, Position
from src.data.binance_client import BinanceClient


@dataclass(slots=True)
class ReconciliationResult:
    matched: bool
    discrepancies: list[str]
    account: Account


class Reconciler:
    def __init__(self, client: BinanceClient, tolerance: Decimal = Decimal("0.0001")):
        self.client = client
        self.tolerance = tolerance

    def reconcile(self, local_account: Account) -> ReconciliationResult:
        discrepancies = []

        try:
            remote_account = self.client.get_account()
            remote_balances = self._parse_balances(remote_account)
            remote_positions = self._parse_positions(remote_account)
        except Exception as e:
            return ReconciliationResult(
                matched=False,
                discrepancies=[f"Failed to fetch remote account: {e}"],
                account=local_account,
            )

        for symbol, local_pos in local_account.positions.items():
            remote_pos = remote_positions.get(symbol)
            if remote_pos is None:
                if local_pos.quantity != 0:
                    discrepancies.append(
                        f"{symbol}: Local position {local_pos.quantity} but remote has no position"
                    )
                continue

            qty_diff = abs(local_pos.quantity - remote_pos.quantity)
            if qty_diff > self.tolerance:
                discrepancies.append(
                    f"{symbol}: Quantity mismatch - "
                    f"local {local_pos.quantity} vs remote {remote_pos.quantity}"
                )

            if local_pos.entry_price and remote_pos.entry_price:
                price_diff = abs(local_pos.entry_price - remote_pos.entry_price)
                if price_diff > self.tolerance:
                    discrepancies.append(
                        f"{symbol}: Entry price mismatch - "
                        f"local {local_pos.entry_price} vs remote {remote_pos.entry_price}"
                    )

        for symbol, remote_pos in remote_positions.items():
            if symbol not in local_account.positions and remote_pos.quantity != 0:
                discrepancies.append(
                    f"{symbol}: Remote has position {remote_pos.quantity} but local has none"
                )

        local_usdt = local_account.available_balance
        remote_usdt = remote_balances.get("USDT", Decimal("0"))
        usdt_diff = abs(local_usdt - remote_usdt)
        if usdt_diff > self.tolerance:
            discrepancies.append(
                f"USDT balance mismatch - local {local_usdt} vs remote {remote_usdt}"
            )

        return ReconciliationResult(
            matched=len(discrepancies) == 0,
            discrepancies=discrepancies,
            account=local_account,
        )

    def _parse_balances(self, account_data: dict) -> dict[str, Decimal]:
        balances = {}
        for b in account_data.get("balances", []):
            asset = b["asset"]
            free = Decimal(b["free"])
            locked = Decimal(b["locked"])
            balances[asset] = free + locked
        return balances

    def _parse_positions(self, account_data: dict) -> dict[str, Position]:
        positions = {}
        for b in account_data.get("balances", []):
            asset = b["asset"]
            if asset == "USDT":
                continue
            free = Decimal(b["free"])
            locked = Decimal(b["locked"])
            total = free + locked
            if total > 0:
                positions[asset] = Position(
                    symbol=f"{asset}USDT",
                    side="LONG" if total > 0 else "FLAT",
                    quantity=total,
                )
        return positions

    def sync_account(self, local_account: Account) -> Account:
        result = self.reconcile(local_account)
        if not result.matched:
            try:
                remote_account = self.client.get_account()
                remote_balances = self._parse_balances(remote_account)

                local_account.available_balance = remote_balances.get("USDT", Decimal("0"))

                for symbol, local_pos in local_account.positions.items():
                    asset = symbol.replace("USDT", "")
                    remote_pos = self._parse_positions(remote_account).get(asset)
                    if remote_pos:
                        local_pos.quantity = remote_pos.quantity
                        local_pos.side = remote_pos.side

            except Exception:
                pass

        return local_account