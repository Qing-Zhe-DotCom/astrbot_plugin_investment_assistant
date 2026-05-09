import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AlertManager:
    VALID_CONDITIONS = (">", "<", ">=", "<=", "+%", "-%")

    def __init__(self, data_dir: Path) -> None:
        self._file = data_dir / "alerts.json"
        self._alerts: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                self._alerts = json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._alerts = []

    def _save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(self._alerts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(
        self,
        symbol: str,
        name: str,
        market: str,
        condition: str,
        target_value: float,
        notes: str = "",
    ) -> dict[str, Any]:
        if condition not in self.VALID_CONDITIONS:
            raise ValueError(f"不支持的条件: {condition}，可选: {', '.join(self.VALID_CONDITIONS)}")

        alert: dict[str, Any] = {
            "id": uuid.uuid4().hex[:10],
            "symbol": symbol.strip().upper(),
            "name": name.strip(),
            "market": market,
            "condition": condition,
            "target_value": target_value,
            "triggered": False,
            "triggered_at": None,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "notes": notes.strip(),
        }
        self._alerts.append(alert)
        self._save()
        return alert

    def remove(self, alert_id: str) -> dict[str, Any] | None:
        for i, a in enumerate(self._alerts):
            if a["id"] == alert_id:
                removed = self._alerts.pop(i)
                self._save()
                return removed
        return None

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._alerts)

    def list_active(self) -> list[dict[str, Any]]:
        return [a for a in self._alerts if not a["triggered"]]

    def mark_triggered(self, alert_id: str) -> None:
        for a in self._alerts:
            if a["id"] == alert_id:
                a["triggered"] = True
                a["triggered_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                self._save()
                return

    def count(self) -> int:
        return len(self._alerts)

    def check_condition(self, alert: dict[str, Any], current_price: float) -> bool:
        cond = alert["condition"]
        target = alert["target_value"]

        if cond == ">":
            return current_price > target
        elif cond == "<":
            return current_price < target
        elif cond == ">=":
            return current_price >= target
        elif cond == "<=":
            return current_price <= target
        elif cond == "+%":
            return current_price >= target
        elif cond == "-%":
            return current_price <= target
        return False
