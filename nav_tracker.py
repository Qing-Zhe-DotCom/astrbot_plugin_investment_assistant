import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class NavTracker:
    def __init__(self, data_dir: Path) -> None:
        self._file = data_dir / "nav_history.json"
        self._snapshots: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                self._snapshots = json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._snapshots = []

    def _save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(self._snapshots, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def snapshot(self, total_value: float, positions: list[dict[str, Any]], indices: list[dict[str, Any]]) -> dict[str, Any]:
        today = datetime.now().strftime("%Y-%m-%d")
        # Deduplicate — only keep latest snapshot for the same day
        self._snapshots = [s for s in self._snapshots if s.get("date") != today]

        snap: dict[str, Any] = {
            "date": today,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_value": round(total_value, 2),
            "position_count": len(positions),
            "positions": [
                {
                    "symbol": p.get("symbol", ""),
                    "name": p.get("name", ""),
                    "market_value": round(p.get("market_value", 0) or 0, 2),
                    "weight": round(
                        (p.get("market_value", 0) or 0) / total_value * 100, 1
                    ) if total_value > 0 else 0,
                }
                for p in positions
            ],
            "indices": [
                {
                    "name": i.get("name", ""),
                    "price": round(i.get("price", 0), 2),
                    "change_pct": round(i.get("change_pct", 0), 2),
                }
                for i in (indices or [])[:5]
            ],
        }
        self._snapshots.append(snap)
        self._save()
        return snap

    def get_history(self, days: int = 30) -> list[dict[str, Any]]:
        return self._snapshots[-days:]

    def latest(self) -> dict[str, Any] | None:
        return self._snapshots[-1] if self._snapshots else None

    def count(self) -> int:
        return len(self._snapshots)

    def summary(self) -> dict[str, Any]:
        if len(self._snapshots) < 2:
            return {
                "period_start": None,
                "period_end": None,
                "start_value": None,
                "end_value": None,
                "change": 0,
                "change_pct": 0,
                "high": None,
                "low": None,
                "trend": "insufficient_data",
            }

        first = self._snapshots[0]
        last = self._snapshots[-1]
        start_val = first["total_value"]
        end_val = last["total_value"]
        change = end_val - start_val

        values = [s["total_value"] for s in self._snapshots]
        high_val = max(values)
        low_val = min(values)

        return {
            "period_start": first["date"],
            "period_end": last["date"],
            "start_value": start_val,
            "end_value": end_val,
            "change": round(change, 2),
            "change_pct": round(change / start_val * 100, 2) if start_val > 0 else 0,
            "high": high_val,
            "low": low_val,
            "trend": "up" if change > 0 else ("down" if change < 0 else "flat"),
        }
