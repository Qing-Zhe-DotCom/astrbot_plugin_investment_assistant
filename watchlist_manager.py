import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class WatchlistManager:
    def __init__(self, data_dir: Path) -> None:
        self._file = data_dir / "watchlist.json"
        self._items: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                self._items = json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._items = []

    def _save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(self._items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(
        self,
        symbol: str,
        name: str,
        market: str,
        notes: str = "",
    ) -> dict[str, Any]:
        VALID_MARKETS = ("A股", "美股", "港股", "虚拟币", "大宗货物")
        if market not in VALID_MARKETS:
            raise ValueError(f"不支持的市场: {market}")

        existing = [i for i in self._items if i["symbol"] == symbol.strip().upper() and i["market"] == market]
        if existing:
            raise ValueError(f"{symbol}({market}) 已在自选列表中")

        item: dict[str, Any] = {
            "id": uuid.uuid4().hex[:10],
            "symbol": symbol.strip().upper(),
            "name": name.strip(),
            "market": market,
            "notes": notes.strip(),
            "added_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._items.append(item)
        self._save()
        return item

    def remove(self, item_id: str) -> dict[str, Any] | None:
        for i, it in enumerate(self._items):
            if it["id"] == item_id:
                removed = self._items.pop(i)
                self._save()
                return removed
        return None

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._items)

    def count(self) -> int:
        return len(self._items)
