import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PortfolioManager:
    VALID_MARKETS = ("A股", "美股", "港股", "虚拟币", "大宗货物")
    VALID_TYPES = ("股票", "ETF", "虚拟币", "商品")
    CURRENCY_MAP = {"A股": "CNY", "美股": "USD", "港股": "HKD", "虚拟币": "USD", "大宗货物": "USD"}

    def __init__(self, data_dir: Path) -> None:
        self._file = data_dir / "portfolio.json"
        self._positions: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                self._positions = json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._positions = []

    def _save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(self._positions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(
        self,
        symbol: str,
        name: str,
        market: str,
        type_: str,
        quantity: float,
        avg_cost: float,
        industry: str = "",
        notes: str = "",
        currency: str = "",
    ) -> dict[str, Any]:
        if market not in self.VALID_MARKETS:
            raise ValueError(f"不支持的市场: {market}，可选: {', '.join(self.VALID_MARKETS)}")
        if type_ not in self.VALID_TYPES:
            raise ValueError(f"不支持的类型: {type_}，可选: {', '.join(self.VALID_TYPES)}")
        if quantity <= 0:
            raise ValueError("数量必须大于0")
        if avg_cost < 0:
            raise ValueError("成本价不能为负数")

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if not currency:
            currency = self.CURRENCY_MAP.get(market, "USD")

        pos: dict[str, Any] = {
            "id": uuid.uuid4().hex[:12],
            "symbol": symbol.strip().upper(),
            "name": name.strip(),
            "market": market,
            "type": type_,
            "industry": industry.strip(),
            "quantity": quantity,
            "avg_cost": avg_cost,
            "currency": currency,
            "notes": notes.strip(),
            "created_at": now,
            "updated_at": now,
        }
        self._positions.append(pos)
        self._save()
        return pos

    def remove(self, pos_id: str) -> dict[str, Any] | None:
        for i, p in enumerate(self._positions):
            if p["id"] == pos_id:
                removed = self._positions.pop(i)
                self._save()
                return removed
        return None

    def update(self, pos_id: str, **fields: Any) -> dict[str, Any] | None:
        pos = self.get(pos_id)
        if pos is None:
            return None
        updatable = {
            "name", "quantity", "avg_cost", "industry",
            "notes", "market", "type", "currency", "symbol",
        }
        for k in updatable:
            if k in fields:
                pos[k] = fields[k]
        pos["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._save()
        return pos

    def get(self, pos_id: str) -> dict[str, Any] | None:
        for p in self._positions:
            if p["id"] == pos_id:
                return p
        return None

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._positions)

    def count(self) -> int:
        return len(self._positions)

    def query(self, market: str = "", type_: str = "", keyword: str = "") -> list[dict[str, Any]]:
        result = self._positions
        if market:
            result = [p for p in result if p["market"] == market]
        if type_:
            result = [p for p in result if p["type"] == type_]
        if keyword:
            kw = keyword.lower()
            result = [
                p for p in result
                if kw in p["name"].lower() or kw in p["symbol"].lower()
            ]
        return result

    def clear(self) -> int:
        count = len(self._positions)
        self._positions = []
        self._save()
        return count
