from collections import defaultdict
from typing import Any


def _calculate_hhi(weights: list[float]) -> float:
    """Herfindahl-Hirschman Index: sum of squared weights (in %), 0-10000."""
    return sum(w * w for w in weights)


def _hhi_interpret(hhi: float) -> str:
    if hhi < 1500:
        return "低度集中 ✅"
    elif hhi < 2500:
        return "中度集中 ⚠️"
    else:
        return "高度集中 🔴"


class PortfolioAnalyzer:
    def __init__(self, risk_threshold: float = 30.0) -> None:
        self.risk_threshold = risk_threshold

    def analyze(self, positions: list[dict[str, Any]]) -> dict[str, Any]:
        total_value = 0.0
        enriched = []
        for p in positions:
            cp = p.get("current_price", 0) or 0
            if cp == 0:
                cp = p.get("avg_cost", 0)
            mv = cp * p.get("quantity", 0)
            pnl = (cp - p.get("avg_cost", 0)) * p.get("quantity", 0)
            pnl_pct = (cp - p.get("avg_cost", 0)) / p["avg_cost"] * 100 if p.get("avg_cost", 0) > 0 else 0
            total_value += mv
            enriched.append({
                **p,
                "current_price": cp,
                "market_value": mv,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            })

        if total_value == 0:
            return {
                "total_value": 0,
                "total_pnl": 0,
                "total_pnl_pct": 0,
                "position_count": len(positions),
                "market_concentration": {},
                "industry_concentration": {},
                "type_concentration": {},
                "risk_warnings": [],
                "positions": enriched,
            }

        total_pnl = sum(p.get("pnl", 0) for p in enriched)
        total_pnl_pct = (total_pnl / (total_value - total_pnl)) * 100 if total_value != total_pnl else 0

        # Market concentration
        market_groups: dict[str, float] = defaultdict(float)
        for p in enriched:
            market_groups[p.get("market", "未知")] += p.get("market_value", 0)
        market_conc = {
            k: {"value": round(v, 2), "pct": round(v / total_value * 100, 1)}
            for k, v in sorted(market_groups.items(), key=lambda x: x[1], reverse=True)
        }
        market_hhi = _calculate_hhi([v / total_value * 100 for v in market_groups.values()])

        # Industry concentration
        industry_groups: dict[str, float] = defaultdict(float)
        for p in enriched:
            ind = p.get("industry", "未分类") or "未分类"
            industry_groups[ind] += p.get("market_value", 0)
        industry_conc = {
            k: {"value": round(v, 2), "pct": round(v / total_value * 100, 1)}
            for k, v in sorted(industry_groups.items(), key=lambda x: x[1], reverse=True)
        }
        industry_hhi = _calculate_hhi([v / total_value * 100 for v in industry_groups.values()])

        # Type concentration
        type_groups: dict[str, float] = defaultdict(float)
        for p in enriched:
            type_groups[p.get("type", "未知")] += p.get("market_value", 0)
        type_conc = {
            k: {"value": round(v, 2), "pct": round(v / total_value * 100, 1)}
            for k, v in sorted(type_groups.items(), key=lambda x: x[1], reverse=True)
        }

        # Currency exposure
        currency_groups: dict[str, float] = defaultdict(float)
        for p in enriched:
            currency_groups[p.get("currency", "USD")] += p.get("market_value", 0)
        currency_exp = {
            k: {"value": round(v, 2), "pct": round(v / total_value * 100, 1)}
            for k, v in sorted(currency_groups.items(), key=lambda x: x[1], reverse=True)
        }

        # Risk warnings
        risk_warnings = []
        for p in enriched:
            pct = p["market_value"] / total_value * 100 if total_value > 0 else 0
            if pct > self.risk_threshold:
                risk_warnings.append(
                    f"🔴 {p['name']}({p['symbol']}) 占比 {pct:.1f}%，"
                    f"超过预警阈值 {self.risk_threshold}%"
                )
            elif pct > self.risk_threshold * 0.7:
                risk_warnings.append(
                    f"🟡 {p['name']}({p['symbol']}) 占比 {pct:.1f}%，"
                    f"接近预警阈值 {self.risk_threshold}%"
                )

        # Market risk: if more than 60% in one market
        for mkt, v in market_conc.items():
            if v["pct"] > 60:
                risk_warnings.append(f"⚠️ 市场集中度偏高: {mkt} 占比 {v['pct']}%")
        for ind, v in industry_conc.items():
            if v["pct"] > 50:
                risk_warnings.append(f"⚠️ 行业集中度偏高: {ind} 占比 {v['pct']}%")

        return {
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "position_count": len(positions),
            "market_concentration": market_conc,
            "market_hhi": round(market_hhi, 1),
            "market_hhi_level": _hhi_interpret(market_hhi),
            "industry_concentration": industry_conc,
            "industry_hhi": round(industry_hhi, 1),
            "industry_hhi_level": _hhi_interpret(industry_hhi),
            "type_concentration": type_conc,
            "currency_exposure": currency_exp,
            "risk_warnings": risk_warnings,
            "positions": enriched,
        }
