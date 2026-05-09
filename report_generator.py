from datetime import datetime
from typing import Any


def _fmt_value(value: float, currency: str = "CNY") -> str:
    if abs(value) >= 1e8:
        return f"{value / 1e8:.2f}亿 {currency}"
    elif abs(value) >= 1e4:
        return f"{value / 1e4:.2f}万 {currency}"
    return f"{value:,.2f} {currency}"


def _fmt_pct(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _pos_row(p: dict[str, Any]) -> str:
    sym = p.get("symbol", "?")
    name = p.get("name", sym)
    qty = p.get("quantity", 0)
    cost = p.get("avg_cost", 0)
    cp = p.get("current_price") or cost
    mv = p.get("market_value") or (cp * qty)
    pnl = p.get("pnl") or (cp - cost) * qty
    pnl_pct = p.get("pnl_pct") or 0
    cur = p.get("currency", "CNY")
    arrow = "📈" if pnl >= 0 else "📉"
    return (
        f"| {sym} | {name} | {qty:,.0f} | {cost:.2f} | {cp:.2f} | "
        f"{_fmt_value(mv, cur)} | {arrow} {_fmt_value(pnl, cur)} | {_fmt_pct(pnl_pct)} |"
    )


class ReportGenerator:
    @staticmethod
    def portfolio_summary(positions: list[dict[str, Any]], analysis: dict[str, Any]) -> str:
        if not positions:
            return "📭 投资组合为空，使用 `/add_position` 添加持仓。"

        total = analysis.get("total_value", 0)
        total_pnl = analysis.get("total_pnl", 0)
        total_pnl_pct = analysis.get("total_pnl_pct", 0)
        currency = positions[0].get("currency", "CNY") if positions else "CNY"
        arrow = "📈" if total_pnl >= 0 else "📉"

        lines = [
            "## 📊 我的投资组合",
            "",
            f"💰 **总市值**: {_fmt_value(total, currency)}",
            f"📊 **总盈亏**: {arrow} {_fmt_value(total_pnl, currency)} ({_fmt_pct(total_pnl_pct)})",
            f"📦 **持仓数量**: {analysis.get('position_count', 0)}",
            "",
            "| 代码 | 名称 | 持仓 | 成本 | 现价 | 市值 | 盈亏 | 涨幅 |",
            "|------|------|------|------|------|------|------|------|",
        ]
        for p in analysis.get("positions", positions):
            lines.append(_pos_row(p))

        if analysis.get("risk_warnings"):
            lines.append("")
            lines.append("### ⚠️ 风险提示")
            for w in analysis["risk_warnings"]:
                lines.append(f"- {w}")

        return "\n".join(lines)

    @staticmethod
    def concentration_report(analysis: dict[str, Any]) -> str:
        if analysis.get("position_count", 0) == 0:
            return "📭 组合为空，无法生成分析。"

        lines = [
            "## 📈 组合集中度分析",
            "",
            "### 🌍 市场分布",
            f"集中度指数(HHI): {analysis.get('market_hhi', 0)} — {analysis.get('market_hhi_level', '')}",
        ]
        for mkt, v in analysis.get("market_concentration", {}).items():
            lines.append(f"- {mkt}: {_fmt_value(v['value'])} ({v['pct']}%)")

        lines += [
            "",
            "### 🏭 行业分布",
            f"集中度指数(HHI): {analysis.get('industry_hhi', 0)} — {analysis.get('industry_hhi_level', '')}",
        ]
        for ind, v in analysis.get("industry_concentration", {}).items():
            lines.append(f"- {ind}: {_fmt_value(v['value'])} ({v['pct']}%)")

        lines += ["", "### 📂 类型分布"]
        for t, v in analysis.get("type_concentration", {}).items():
            lines.append(f"- {t}: {_fmt_value(v['value'])} ({v['pct']}%)")

        if analysis.get("currency_exposure"):
            lines += ["", "### 💱 货币敞口"]
            for cur, v in analysis["currency_exposure"].items():
                lines.append(f"- {cur}: {v['pct']}%")

        return "\n".join(lines)

    @staticmethod
    def risk_report(analysis: dict[str, Any]) -> str:
        if analysis.get("position_count", 0) == 0:
            return "📭 组合为空。"

        lines = [
            "## 🛡️ 风险评估报告",
            "",
            f"**持仓数量**: {analysis['position_count']}",
            f"**总市值**: {_fmt_value(analysis.get('total_value', 0))}",
        ]

        warnings = analysis.get("risk_warnings", [])
        if warnings:
            lines += ["", "### ⚠️ 风险预警"]
            for w in warnings:
                lines.append(f"- {w}")
        else:
            lines += ["", "### ✅ 暂无风险预警", "组合持仓分散，未触发集中度预警阈值。"]

        lines += [
            "",
            "### 📋 单标的风险敞口",
        ]
        for p in analysis.get("positions", []):
            mv = p.get("market_value") or 0
            total = analysis.get("total_value", 1)
            pct = mv / total * 100 if total > 0 else 0
            bar = "█" * min(int(pct), 50)
            lines.append(f"- {p['name']}({p['symbol']}): {pct:.1f}% {bar}")

        return "\n".join(lines)

    @staticmethod
    def daily_report(positions: list[dict[str, Any]], analysis: dict[str, Any], indices: list[dict[str, Any]]) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [
            f"## 📅 每日投资报告 — {today}",
            "",
        ]

        # Indices
        if indices:
            lines.append("### 🌏 主要指数")
            for idx in indices[:6]:
                sign = "+" if idx.get("change_pct", 0) >= 0 else ""
                lines.append(f"- {idx['name']}: {idx['price']:.2f} ({sign}{idx['change_pct']:.2f}%)")
            lines.append("")

        # Portfolio perf
        total_pnl = analysis.get("total_pnl", 0)
        total_pnl_pct = analysis.get("total_pnl_pct", 0)
        arrow = "📈" if total_pnl >= 0 else "📉"
        lines += [
            f"### 💼 组合表现",
            f"总市值: {_fmt_value(analysis.get('total_value', 0))}",
            f"当日盈亏: {arrow} {_fmt_value(total_pnl)} ({_fmt_pct(total_pnl_pct)})",
            "",
            "### 📊 持仓明细",
            "| 名称 | 现价 | 涨跌 | 市值 | 盈亏 |",
            "|------|------|------|------|------|",
        ]
        for p in analysis.get("positions", []):
            sym = p.get("symbol", "?")
            name = p.get("name", sym)
            mv = p.get("market_value") or 0
            pnl = p.get("pnl") or 0
            cp = p.get("current_price") or 0
            chg = p.get("change_pct") or 0
            chg_str = _fmt_pct(chg)
            pnl_str = _fmt_value(pnl, p.get("currency", "CNY"))
            lines.append(f"| {name}({sym}) | {cp:.2f} | {chg_str} | {_fmt_value(mv, p.get('currency', 'CNY'))} | {pnl_str} |")

        if analysis.get("risk_warnings"):
            lines += ["", "### ⚠️ 风险提示"]
            for w in analysis["risk_warnings"]:
                lines.append(f"- {w}")

        return "\n".join(lines)

    @staticmethod
    def weekly_report(analysis: dict[str, Any], start_date: str, end_date: str) -> str:
        lines = [
            f"## 📊 周度投资报告 — {start_date} ~ {end_date}",
            "",
            f"### 💼 组合概览",
            f"总市值: {_fmt_value(analysis.get('total_value', 0))}",
            f"持仓数量: {analysis.get('position_count', 0)}",
            f"总盈亏: {_fmt_value(analysis.get('total_pnl', 0))} ({_fmt_pct(analysis.get('total_pnl_pct', 0))})",
            "",
            "### 📈 表现最佳",
        ]
        positions = sorted(analysis.get("positions", []), key=lambda x: x.get("pnl_pct", 0) or 0, reverse=True)
        for p in positions[:3]:
            lines.append(f"- {p['name']}({p['symbol']}): {_fmt_pct(p.get('pnl_pct', 0))}")

        lines += ["", "### 📉 表现最差"]
        for p in positions[-3:]:
            lines.append(f"- {p['name']}({p['symbol']}): {_fmt_pct(p.get('pnl_pct', 0))}")

        lines += [
            "",
            "### 🌍 市场分布",
        ]
        for mkt, v in analysis.get("market_concentration", {}).items():
            lines.append(f"- {mkt}: {v['pct']}%")

        if analysis.get("risk_warnings"):
            lines += ["", "### ⚠️ 风险提示"]
            for w in analysis["risk_warnings"]:
                lines.append(f"- {w}")

        return "\n".join(lines)

    @staticmethod
    def monthly_report(analysis: dict[str, Any], month: str) -> str:
        lines = [
            f"## 📋 月度投资报告 — {month}",
            "",
            f"### 💼 组合概览",
            f"总市值: {_fmt_value(analysis.get('total_value', 0))}",
            f"持仓数量: {analysis.get('position_count', 0)}",
            f"总盈亏: {_fmt_value(analysis.get('total_pnl', 0))} ({_fmt_pct(analysis.get('total_pnl_pct', 0))})",
            "",
            "### 🌍 市场分布",
        ]
        for mkt, v in analysis.get("market_concentration", {}).items():
            lines.append(f"- {mkt}: {v['pct']}%")

        lines += ["", "### 🏭 行业分布"]
        for ind, v in analysis.get("industry_concentration", {}).items():
            lines.append(f"- {ind}: {v['pct']}%")

        lines += [
            "",
            "### 📂 类型分布",
        ]
        for t, v in analysis.get("type_concentration", {}).items():
            lines.append(f"- {t}: {v['pct']}%")

        lines += [
            "",
            "### 💱 货币敞口",
        ]
        for cur, v in analysis.get("currency_exposure", {}).items():
            lines.append(f"- {cur}: {v['pct']}%")

        if analysis.get("risk_warnings"):
            lines += ["", "### ⚠️ 风险提示"]
            for w in analysis["risk_warnings"]:
                lines.append(f"- {w}")

        return "\n".join(lines)
