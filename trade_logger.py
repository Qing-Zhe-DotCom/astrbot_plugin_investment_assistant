import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TradeLogger:
    VALID_TYPES = ("buy", "sell")

    def __init__(self, data_dir: Path) -> None:
        self._file = data_dir / "trades.json"
        self._trades: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                self._trades = json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._trades = []

    def _save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(self._trades, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record(
        self,
        trade_type: str,
        symbol: str,
        name: str,
        market: str,
        price: float,
        quantity: float,
        date: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        if trade_type not in self.VALID_TYPES:
            raise ValueError(f"交易类型只能为 buy 或 sell，收到: {trade_type}")
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        amount = round(price * quantity, 2)
        trade: dict[str, Any] = {
            "id": uuid.uuid4().hex[:10],
            "type": trade_type,
            "symbol": symbol.strip().upper(),
            "name": name.strip(),
            "market": market,
            "price": price,
            "quantity": quantity,
            "amount": amount,
            "date": date,
            "notes": notes.strip(),
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._trades.append(trade)
        self._save()
        return trade

    def remove(self, trade_id: str) -> dict[str, Any] | None:
        for i, t in enumerate(self._trades):
            if t["id"] == trade_id:
                removed = self._trades.pop(i)
                self._save()
                return removed
        return None

    def list_all(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(reversed(self._trades))[:limit]

    def list_by_symbol(self, symbol: str) -> list[dict[str, Any]]:
        return [t for t in self._trades if t["symbol"] == symbol.strip().upper()]

    def count(self) -> int:
        return len(self._trades)

    def summary(self) -> dict[str, Any]:
        total_buy = 0.0
        total_sell = 0.0
        by_symbol: dict[str, dict[str, Any]] = {}

        for t in self._trades:
            sym = t["symbol"]
            if sym not in by_symbol:
                by_symbol[sym] = {
                    "symbol": sym,
                    "name": t["name"],
                    "market": t["market"],
                    "total_buy_qty": 0.0,
                    "total_buy_amount": 0.0,
                    "total_sell_qty": 0.0,
                    "total_sell_amount": 0.0,
                }

            if t["type"] == "buy":
                total_buy += t["amount"]
                by_symbol[sym]["total_buy_qty"] += t["quantity"]
                by_symbol[sym]["total_buy_amount"] += t["amount"]
            else:
                total_sell += t["amount"]
                by_symbol[sym]["total_sell_qty"] += t["quantity"]
                by_symbol[sym]["total_sell_amount"] += t["amount"]

        # Calculate avg cost and realized P&L per symbol
        for sym, data in by_symbol.items():
            if data["total_buy_qty"] > 0:
                data["avg_buy_price"] = round(data["total_buy_amount"] / data["total_buy_qty"], 2)
            else:
                data["avg_buy_price"] = 0
            if data["total_sell_qty"] > 0:
                data["avg_sell_price"] = round(data["total_sell_amount"] / data["total_sell_qty"], 2)
            else:
                data["avg_sell_price"] = 0
            data["net_qty"] = round(data["total_buy_qty"] - data["total_sell_qty"], 4)
            data["realized_pnl"] = round(
                data["total_sell_amount"] - data["avg_buy_price"] * data["total_sell_qty"], 2
            )

        return {
            "trade_count": len(self._trades),
            "total_buy_amount": round(total_buy, 2),
            "total_sell_amount": round(total_sell, 2),
            "net_cash_flow": round(total_sell - total_buy, 2),
            "by_symbol": list(by_symbol.values()),
        }
