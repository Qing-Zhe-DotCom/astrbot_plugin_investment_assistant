import asyncio
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent, MessageChain, MessageEventResult
from astrbot.api.star import Context, Star, StarTools
from astrbot.api import AstrBotConfig, logger

from .portfolio_manager import PortfolioManager
from .market_data import AssetResolver, MarketDataProvider
from .analysis import PortfolioAnalyzer
from .report_generator import ReportGenerator
from .alert_manager import AlertManager
from .nav_tracker import NavTracker
from .trade_logger import TradeLogger
from .watchlist_manager import WatchlistManager


class InvestmentAssistant(Star):
    """投资助手插件 — 组合管理 / 分析 / 盯盘报告"""

    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config

        data_dir = StarTools.get_data_dir()
        self.pm = PortfolioManager(data_dir)
        self.mdp = MarketDataProvider()
        self.resolver = AssetResolver()
        risk_threshold = float(config.get("risk_warning_threshold", 30.0))
        self.analyzer = PortfolioAnalyzer(risk_threshold=risk_threshold)
        self.reporter = ReportGenerator()
        self.alert_mgr = AlertManager(data_dir)
        self.nav_tracker = NavTracker(data_dir)
        self.trade_logger = TradeLogger(data_dir)
        self.watchlist = WatchlistManager(data_dir)

    async def initialize(self) -> None:
        await self._setup_cron_jobs()

    async def terminate(self) -> None:
        pass

    # ── Helper ───────────────────────────────────────────────

    async def _get_enriched_analysis(self) -> dict:
        positions = self.pm.list_all()
        enriched = await self.mdp.get_batch(positions)
        return self.analyzer.analyze(enriched)

    def _usage_add(self) -> str:
        return (
            "🔹 **智能添加** (推荐): `/add_position <代码> <成本价> <数量> [备注]`\n"
            "　系统自动识别市场、名称、类型、行业。\n"
            "　例: `/add_position 600519 1800 100`\n"
            "　例: `/add_position AAPL 180 50`\n"
            "　例: `/add_position BTC 65000 0.5`\n\n"
            "🔹 **手动添加** (全参数): `/add_position <代码> <名称> <市场> <类型> <数量> <成本价> [行业] [备注]`\n"
            "　市场: A股 | 美股 | 港股 | 虚拟币 | 大宗货物\n"
            "　类型: 股票 | ETF | 虚拟币 | 商品"
        )

    def _usage_edit(self) -> str:
        return "用法: `/edit_position <ID> <字段> <值>`\n字段: name | quantity | avg_cost | industry | notes"

    def _usage_alert(self) -> str:
        return (
            "🔔 **价格预警**:\n"
            "`/alert add <代码> <名称> <市场> <条件> <目标值> [备注]` — 添加预警\n"
            "`/alert list` — 查看所有预警\n"
            "`/alert del <ID>` — 删除预警\n\n"
            "条件: `>` 高于 | `<` 低于 | `>=` 达到 | `<=` 跌破 | `+%` 涨幅超 | `-%` 跌幅超\n"
            "例: `/alert add 600519 贵州茅台 A股 > 2000 突破2000提醒`\n"
            "例: `/alert add AAPL Apple 美股 -% 180 跌破180提醒`"
        )

    def _usage_watch(self) -> str:
        return (
            "⭐ **自选股**:\n"
            "`/watch add <代码> <名称> <市场> [备注]` — 添加自选\n"
            "`/watch list` — 查看自选列表\n"
            "`/watch del <ID>` — 删除自选\n"
            "例: `/watch add TSLA 特斯拉 美股 关注电动车`"
        )

    def _usage_trade(self) -> str:
        return (
            "📒 **交易记录**:\n"
            "`/trade buy <代码> <名称> <市场> <价格> <数量> [日期] [备注]` — 记录买入\n"
            "`/trade sell <代码> <名称> <市场> <价格> <数量> [日期] [备注]` — 记录卖出\n"
            "`/trade log [条数]` — 查看最近交易 (默认20条)\n"
            "`/trade summary` — 交易汇总 (已实现盈亏)\n"
            "例: `/trade buy AAPL Apple 美股 195 50 2025-01-15 建仓`\n"
            "例: `/trade sell AAPL Apple 美股 210 30 2025-03-20 止盈`"
        )

    def _usage_nav(self) -> str:
        return (
            "📈 **净值追踪**:\n"
            "`/nav` — 查看最新净值快照\n"
            "`/nav history [天数]` — 查看净值历史曲线 (默认30天)\n"
            "例: `/nav history 7`"
        )

    async def _resolve_and_add(
        self, symbol: str, cost: float, quantity: float, notes: str = ""
    ) -> str:
        """Resolve an asset and add it to the portfolio. Returns a user-facing message."""

        result = await self.resolver.resolve(symbol)

        if not result["resolved"]:
            return f"❌ {result['suggestion']}"

        if result["ambiguity"] == "high":
            lines = [result["suggestion"]]
            lines.append("\n💡 请使用更精确的代码重新添加，或使用手动格式:")
            lines.append(
                "`/add_position <代码> <名称> <市场> <类型> "
                f"{quantity} {cost}`"
            )
            return "\n".join(lines)

        match = result["best_match"]
        # Try to enrich with industry for A-shares
        if match["market"] == "A股" and not match.get("industry"):
            try:
                industry = await self.resolver._resolve_a_share_industry(match["symbol"])
                if industry:
                    match["industry"] = industry
            except Exception:
                pass

        try:
            pos = self.pm.add(
                symbol=match["symbol"],
                name=match["name"],
                market=match["market"],
                type_=match["type"],
                quantity=quantity,
                avg_cost=cost,
                industry=match.get("industry", ""),
                notes=notes,
            )
        except ValueError as e:
            return f"❌ 添加失败: {e}"

        industry_str = f" · {pos['industry']}" if pos["industry"] else ""
        return (
            f"✅ 已智能添加持仓:\n"
            f"ID: `{pos['id']}`\n"
            f"代码: {pos['symbol']} | 名称: {pos['name']}\n"
            f"市场: {pos['market']} | 类型: {pos['type']}{industry_str}\n"
            f"数量: {pos['quantity']} | 成本价: {pos['avg_cost']}\n"
            f"识别来源: {match.get('source', 'unknown')}"
        )

    # ── Commands ─────────────────────────────────────────────

    @filter.command("add_position")
    async def cmd_add_position(self, event: AstrMessageEvent) -> MessageEventResult:
        """智能添加投资持仓——只需代码+成本+数量，自动识别市场和行业"""
        text = event.message_str.strip()
        cmd = text.split()[0]
        args = text[len(cmd):].strip().split()
        if len(args) < 3:
            yield event.plain_result(self._usage_add())
            return

        # Detect format: new (symbol cost quantity) vs old (symbol name market type quantity cost ...)
        # If args[1] looks like a number, it's the new smart format
        try:
            float(args[1])
            is_smart = True
        except ValueError:
            is_smart = False

        if is_smart and len(args) < 3:
            yield event.plain_result(self._usage_add())
            return

        if is_smart:
            symbol = args[0]
            try:
                cost = float(args[1])
                quantity = float(args[2])
            except ValueError:
                yield event.plain_result("成本价和数量必须是数字。")
                return
            notes = " ".join(args[3:]) if len(args) > 3 else ""

            yield event.plain_result(f"🔍 正在识别「{symbol}」...")
            msg = await self._resolve_and_add(symbol, cost, quantity, notes)
            yield event.plain_result(msg)
        else:
            # Full manual format (backward compatible)
            if len(args) < 6:
                yield event.plain_result(f"参数不足。\n{self._usage_add()}")
                return
            symbol = args[0]
            name = args[1]
            market = args[2]
            type_ = args[3]
            try:
                quantity = float(args[4])
                avg_cost = float(args[5])
            except ValueError:
                yield event.plain_result("数量和成本价必须是数字。")
                return
            industry = args[6] if len(args) > 6 else ""
            notes = " ".join(args[7:]) if len(args) > 7 else ""
            try:
                pos = self.pm.add(symbol, name, market, type_, quantity, avg_cost, industry, notes)
            except ValueError as e:
                yield event.plain_result(f"添加失败: {e}")
                return
            yield event.plain_result(
                f"✅ 已添加持仓:\n"
                f"ID: {pos['id']}\n"
                f"代码: {pos['symbol']}\n"
                f"名称: {pos['name']}\n"
                f"市场: {pos['market']} | 类型: {pos['type']}\n"
                f"数量: {pos['quantity']} | 成本: {pos['avg_cost']}\n"
                f"行业: {pos['industry'] or '未设置'}"
            )

    @filter.command("del_position")
    async def cmd_del_position(self, event: AstrMessageEvent) -> MessageEventResult:
        """删除投资组合中的持仓"""
        text = event.message_str.strip()
        parts = text.split()
        if len(parts) < 2:
            yield event.plain_result("用法: `/del_position <ID>`\n使用 `/my_portfolio` 查看所有持仓ID。")
            return
        pos_id = parts[1]
        removed = self.pm.remove(pos_id)
        if removed:
            yield event.plain_result(f"✅ 已删除持仓: {removed['name']}({removed['symbol']})")
        else:
            yield event.plain_result(f"❌ 未找到持仓 ID: {pos_id}")

    @filter.command("edit_position")
    async def cmd_edit_position(self, event: AstrMessageEvent) -> MessageEventResult:
        """编辑持仓信息"""
        text = event.message_str.strip()
        cmd = text.split()[0]
        args = text[len(cmd):].strip().split()
        if len(args) < 3:
            yield event.plain_result(self._usage_edit())
            return
        pos_id = args[0]
        field = args[1]
        value = " ".join(args[2:])
        valid_fields = {"name", "quantity", "avg_cost", "industry", "notes"}
        if field not in valid_fields:
            yield event.plain_result(f"不可编辑的字段: {field}。可编辑: {', '.join(sorted(valid_fields))}")
            return
        if field in ("quantity", "avg_cost"):
            try:
                value = float(value)  # type: ignore[assignment]
            except ValueError:
                yield event.plain_result("数量/成本价必须是数字。")
                return

        updated = self.pm.update(pos_id, **{field: value})
        if updated:
            yield event.plain_result(f"✅ 已更新 {updated['name']}({updated['symbol']}) 的 {field} = {value}")
        else:
            yield event.plain_result(f"❌ 未找到持仓 ID: {pos_id}")

    @filter.command("my_portfolio")
    async def cmd_my_portfolio(self, event: AstrMessageEvent) -> MessageEventResult:
        """查看我的投资组合"""
        positions = self.pm.list_all()
        if not positions:
            yield event.plain_result("📭 投资组合为空。\n使用 `/add_position` 添加持仓。")
            return

        yield event.plain_result("⏳ 正在获取实时行情...")

        enriched = await self.mdp.get_batch(positions)
        analysis = self.analyzer.analyze(enriched)
        report = self.reporter.portfolio_summary(positions, analysis)
        yield event.plain_result(report)

    @filter.command("portfolio_analysis")
    async def cmd_portfolio_analysis(self, event: AstrMessageEvent) -> MessageEventResult:
        """投资组合分析与风险评估"""
        text = event.message_str.strip()
        parts = text.split()
        sub = parts[1].lower() if len(parts) > 1 else "full"

        positions = self.pm.list_all()
        if not positions:
            yield event.plain_result("📭 投资组合为空。")
            return

        yield event.plain_result("⏳ 正在分析...")

        enriched = await self.mdp.get_batch(positions)
        analysis = self.analyzer.analyze(enriched)

        if sub == "concentration" or sub == "集中度":
            report = self.reporter.concentration_report(analysis)
        elif sub == "risk" or sub == "风险":
            report = self.reporter.risk_report(analysis)
        elif sub == "full":
            report = self.reporter.portfolio_summary(positions, analysis) + "\n\n" + self.reporter.concentration_report(analysis) + "\n\n" + self.reporter.risk_report(analysis)
        else:
            report = self.reporter.portfolio_summary(positions, analysis)

        yield event.plain_result(report)

    @filter.command("market_watch")
    async def cmd_market_watch(self, event: AstrMessageEvent) -> MessageEventResult:
        """实时行情盯盘"""
        text = event.message_str.strip()
        parts = text.split()

        if len(parts) > 1:
            # Watch specific symbol
            symbol = parts[1]
            market = parts[2] if len(parts) > 2 else "A股"
            quote = await self.mdp.get_quote(symbol, market)
            if quote:
                sign = "+" if quote.get("change_pct", 0) >= 0 else ""
                lines = [
                    f"## 📈 {quote['name']}({quote['symbol']})",
                    f"市场: {quote['market']} | 币种: {quote.get('currency', '?')}",
                    f"现价: {quote['price']:.2f}",
                    f"涨跌: {sign}{quote.get('change_pct', 0):.2f}%",
                ]
                if "high" in quote and "low" in quote:
                    lines.append(f"最高: {quote['high']:.2f} | 最低: {quote['low']:.2f}")
                if "volume" in quote:
                    lines.append(f"成交量: {quote.get('volume', 0):,.0f}")
                yield event.plain_result("\n".join(lines))
            else:
                yield event.plain_result(f"❌ 获取 {symbol}({market}) 行情失败。")
        else:
            # Watch full portfolio
            positions = self.pm.list_all()
            if not positions:
                yield event.plain_result("📭 组合为空。用法: `/market_watch <代码> [市场]`")
                return

            yield event.plain_result("⏳ 正在获取行情...")
            enriched = await self.mdp.get_batch(positions)

            # Also get indices
            indices = await self.mdp.get_indices()

            lines = ["## 📈 实时盯盘", ""]
            if indices:
                lines.append("### 🌏 主要指数")
                for idx in indices[:6]:
                    sign = "+" if idx.get("change_pct", 0) >= 0 else ""
                    lines.append(f"- {idx['name']}: {idx['price']:.2f} ({sign}{idx['change_pct']:.2f}%)")
                lines.append("")

            lines += ["### 💼 持仓行情", "| 名称 | 现价 | 涨跌 | 市值 | 盈亏 |", "|------|------|------|------|------|"]
            for p in enriched:
                cp = p.get("current_price") or p.get("avg_cost", 0)
                chg = p.get("change_pct") or 0
                mv = p.get("market_value") or (cp * p.get("quantity", 0))
                pnl = p.get("pnl") or 0
                cur = p.get("currency", "CNY")
                chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
                pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"
                lines.append(f"| {p['name']}({p['symbol']}) | {cp:.2f} | {chg_str} | {mv:.2f}{cur} | {pnl_str}{cur} |")

            yield event.plain_result("\n".join(lines))

    @filter.command("investment_report")
    async def cmd_investment_report(self, event: AstrMessageEvent) -> MessageEventResult:
        """生成投资报告 (daily/weekly/monthly)"""
        text = event.message_str.strip()
        parts = text.split()
        report_type = parts[1].lower() if len(parts) > 1 else "daily"

        positions = self.pm.list_all()
        if not positions:
            yield event.plain_result("📭 组合为空。")
            return

        yield event.plain_result("⏳ 正在生成报告...")

        enriched = await self.mdp.get_batch(positions)
        analysis = self.analyzer.analyze(enriched)
        indices = await self.mdp.get_indices()

        if report_type == "daily":
            report = self.reporter.daily_report(positions, analysis, indices)
        elif report_type == "weekly" or report_type == "周报":
            end = datetime.now()
            start = end - timedelta(days=7)
            report = self.reporter.weekly_report(analysis, start.strftime("%m-%d"), end.strftime("%m-%d"))
        elif report_type == "monthly" or report_type == "月报":
            report = self.reporter.monthly_report(analysis, datetime.now().strftime("%Y年%m月"))
        else:
            report = self.reporter.daily_report(positions, analysis, indices)

        yield event.plain_result(report)

    # ── Price Alerts ─────────────────────────────────────────

    @filter.command("alert")
    async def cmd_alert(self, event: AstrMessageEvent) -> MessageEventResult:
        """价格预警管理"""
        text = event.message_str.strip()
        cmd = text.split()[0]
        args = text[len(cmd):].strip().split()

        if not args:
            yield event.plain_result(self._usage_alert())
            return

        sub = args[0].lower()

        if sub == "add":
            if len(args) < 6:
                yield event.plain_result(self._usage_alert())
                return
            symbol = args[1]
            name = args[2]
            market = args[3]
            condition = args[4]
            try:
                target_value = float(args[5])
            except ValueError:
                yield event.plain_result("目标值必须是数字。")
                return
            notes = " ".join(args[6:]) if len(args) > 6 else ""
            try:
                alert = self.alert_mgr.add(symbol, name, market, condition, target_value, notes)
            except ValueError as e:
                yield event.plain_result(f"添加预警失败: {e}")
                return
            yield event.plain_result(
                f"🔔 已添加价格预警:\n"
                f"ID: `{alert['id']}`\n"
                f"标的: {alert['name']}({alert['symbol']}) · {alert['market']}\n"
                f"条件: {alert['condition']} {alert['target_value']}\n"
                f"状态: {'已触发' if alert['triggered'] else '监控中'}"
            )

        elif sub == "list":
            alerts = self.alert_mgr.list_all()
            if not alerts:
                yield event.plain_result("📭 暂无价格预警。")
                return
            lines = ["## 🔔 价格预警列表", ""]
            for a in alerts:
                status = "🔴 已触发" if a["triggered"] else "🟢 监控中"
                triggered = f" (触发于 {a['triggered_at']})" if a.get("triggered_at") else ""
                lines.append(
                    f"- `{a['id']}` {status}{triggered}\n"
                    f"  {a['name']}({a['symbol']}) · {a['market']} | "
                    f"{a['condition']} {a['target_value']}"
                )
                if a.get("notes"):
                    lines.append(f"  备注: {a['notes']}")
            yield event.plain_result("\n".join(lines))

        elif sub == "del" or sub == "delete":
            if len(args) < 2:
                yield event.plain_result("用法: `/alert del <ID>`")
                return
            removed = self.alert_mgr.remove(args[1])
            if removed:
                yield event.plain_result(f"✅ 已删除预警: {removed['name']}({removed['symbol']})")
            else:
                yield event.plain_result(f"❌ 未找到预警 ID: {args[1]}")

        else:
            yield event.plain_result(self._usage_alert())

    # ── Benchmark Comparison ──────────────────────────────────

    @filter.command("benchmark")
    async def cmd_benchmark(self, event: AstrMessageEvent) -> MessageEventResult:
        """投资组合 vs 基准指数对比"""
        positions = self.pm.list_all()
        if not positions:
            yield event.plain_result("📭 组合为空，无法进行基准对比。")
            return

        yield event.plain_result("⏳ 正在计算基准对比...")

        enriched = await self.mdp.get_batch(positions)
        analysis = self.analyzer.analyze(enriched)
        indices = await self.mdp.get_indices()

        lines = ["## 📊 基准对比分析", ""]

        # Portfolio performance
        total_pnl = analysis.get("total_pnl", 0)
        total_pnl_pct = analysis.get("total_pnl_pct", 0)
        total_value = analysis.get("total_value", 0)
        arrow = "📈" if total_pnl >= 0 else "📉"

        lines += [
            "### 💼 我的组合",
            f"总市值: {total_value:,.2f}",
            f"总盈亏: {arrow} {total_pnl:,.2f} ({total_pnl_pct:+.2f}%)",
            "",
            "### 🌏 基准指数对比",
            "",
            "| 指数 | 现价 | 涨跌 | 对比组合 |",
            "|------|------|------|----------|",
        ]

        for idx in indices[:6]:
            idx_pct = idx.get("change_pct", 0)
            delta = total_pnl_pct - idx_pct
            beat = "✅ 跑赢" if delta > 0 else ("🔴 跑输" if delta < 0 else "➖ 持平")
            idx_sign = "+" if idx_pct >= 0 else ""
            lines.append(
                f"| {idx['name']} | {idx['price']:.2f} | {idx_sign}{idx_pct:.2f}% | "
                f"{beat} ({delta:+.2f}%) |"
            )

        # NAV trend summary if available
        nav_summary = self.nav_tracker.summary()
        if nav_summary.get("period_start"):
            lines += [
                "",
                "### 📈 净值变化趋势",
                f"周期: {nav_summary['period_start']} ~ {nav_summary['period_end']}",
                f"起始净值: {nav_summary['start_value']:,.2f}",
                f"当前净值: {nav_summary['end_value']:,.2f}",
                f"变化: {nav_summary['change']:+,.2f} ({nav_summary['change_pct']:+.2f}%)",
                f"最高: {nav_summary['high']:,.2f} | 最低: {nav_summary['low']:,.2f}",
                f"趋势: {'📈 上升' if nav_summary.get('trend') == 'up' else ('📉 下降' if nav_summary.get('trend') == 'down' else '➖ 持平')}",
            ]

        yield event.plain_result("\n".join(lines))

    # ── Watchlist ─────────────────────────────────────────────

    @filter.command("watch")
    async def cmd_watch(self, event: AstrMessageEvent) -> MessageEventResult:
        """自选股管理"""
        text = event.message_str.strip()
        cmd = text.split()[0]
        args = text[len(cmd):].strip().split()

        if not args:
            yield event.plain_result(self._usage_watch())
            return

        sub = args[0].lower()

        if sub == "add":
            if len(args) < 4:
                yield event.plain_result(self._usage_watch())
                return
            symbol = args[1]
            name = args[2]
            market = args[3]
            notes = " ".join(args[4:]) if len(args) > 4 else ""
            try:
                item = self.watchlist.add(symbol, name, market, notes)
            except ValueError as e:
                yield event.plain_result(f"添加自选失败: {e}")
                return
            yield event.plain_result(
                f"⭐ 已添加到自选:\n"
                f"ID: `{item['id']}`\n"
                f"代码: {item['symbol']} | 名称: {item['name']}\n"
                f"市场: {item['market']}"
            )

        elif sub == "list":
            items = self.watchlist.list_all()
            if not items:
                yield event.plain_result("📭 自选列表为空。")
                return

            yield event.plain_result("⏳ 正在获取自选行情...")

            lines = ["## ⭐ 自选股行情", "", "| 名称 | 代码 | 市场 | 现价 | 涨跌 |", "|------|------|------|------|------|"]
            for it in items:
                quote = await self.mdp.get_quote(it["symbol"], it["market"])
                if quote:
                    cp = quote.get("price", 0)
                    chg = quote.get("change_pct", 0)
                    chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
                    lines.append(f"| {it['name']} | {it['symbol']} | {it['market']} | {cp:.2f} | {chg_str} |")
                else:
                    lines.append(f"| {it['name']} | {it['symbol']} | {it['market']} | N/A | N/A |")

            yield event.plain_result("\n".join(lines))

        elif sub == "del" or sub == "delete":
            if len(args) < 2:
                yield event.plain_result("用法: `/watch del <ID>`")
                return
            removed = self.watchlist.remove(args[1])
            if removed:
                yield event.plain_result(f"✅ 已从自选移除: {removed['name']}({removed['symbol']})")
            else:
                yield event.plain_result(f"❌ 未找到自选 ID: {args[1]}")

        else:
            yield event.plain_result(self._usage_watch())

    # ── NAV Curve ─────────────────────────────────────────────

    @filter.command("nav")
    async def cmd_nav(self, event: AstrMessageEvent) -> MessageEventResult:
        """净值追踪"""
        text = event.message_str.strip()
        parts = text.split()

        if len(parts) > 1 and parts[1].lower() in ("history", "历史"):
            days = 30
            if len(parts) > 2:
                try:
                    days = int(parts[2])
                except ValueError:
                    days = 30
            days = min(days, 365)

            history = self.nav_tracker.get_history(days)
            if not history:
                yield event.plain_result("📭 暂无净值历史数据。每日收盘后自动记录。")
                return

            lines = [f"## 📈 净值历史曲线 (近{days}天)", ""]
            lines.append("| 日期 | 总净值 | 持仓数 | 指数 |")
            lines.append("|------|--------|--------|------|")
            for snap in history:
                date = snap.get("date", "?")
                tv = snap.get("total_value", 0)
                pc = snap.get("position_count", 0)
                idx_str = ", ".join(
                    f"{i['name']}: {i['price']:.0f}" for i in (snap.get("indices") or [])[:2]
                )
                lines.append(f"| {date} | {tv:,.2f} | {pc} | {idx_str} |")

            nav_summary = self.nav_tracker.summary()
            if nav_summary.get("period_start"):
                lines += [
                    "",
                    f"周期: {nav_summary['period_start']} ~ {nav_summary['period_end']}",
                    f"变化: {nav_summary['change']:+,.2f} ({nav_summary['change_pct']:+.2f}%)",
                    f"最高: {nav_summary['high']:,.2f} | 最低: {nav_summary['low']:,.2f}",
                ]

            yield event.plain_result("\n".join(lines))
        else:
            latest = self.nav_tracker.latest()
            if not latest:
                yield event.plain_result("📭 暂无净值快照。每日收盘后自动记录，或使用 `/nav history` 查看历史。")
                return

            lines = [
                f"## 📈 最新净值快照",
                f"日期: {latest['date']}",
                f"总净值: {latest['total_value']:,.2f}",
                f"持仓数量: {latest['position_count']}",
                "",
                "### 📊 持仓权重",
            ]
            for p in latest.get("positions", []):
                lines.append(f"- {p['name']}({p['symbol']}): {p['market_value']:,.2f} ({p['weight']}%)")

            if latest.get("indices"):
                lines += ["", "### 🌏 同期指数"]
                for idx in latest["indices"]:
                    sign = "+" if idx.get("change_pct", 0) >= 0 else ""
                    lines.append(f"- {idx['name']}: {idx['price']:.2f} ({sign}{idx['change_pct']:.2f}%)")

            yield event.plain_result("\n".join(lines))

    # ── Trade Log ─────────────────────────────────────────────

    @filter.command("trade")
    async def cmd_trade(self, event: AstrMessageEvent) -> MessageEventResult:
        """交易记录管理"""
        text = event.message_str.strip()
        cmd = text.split()[0]
        args = text[len(cmd):].strip().split()

        if not args:
            yield event.plain_result(self._usage_trade())
            return

        sub = args[0].lower()

        if sub in ("buy", "sell"):
            if len(args) < 6:
                yield event.plain_result(self._usage_trade())
                return
            trade_type = sub
            symbol = args[1]
            name = args[2]
            market = args[3]
            try:
                price = float(args[4])
                quantity = float(args[5])
            except ValueError:
                yield event.plain_result("价格和数量必须是数字。")
                return
            # Optional date and notes
            date = ""
            notes_start = 6
            if len(args) > 6:
                if re.match(r"^\d{4}-\d{2}-\d{2}$", args[6]):
                    date = args[6]
                    notes_start = 7
            notes = " ".join(args[notes_start:]) if len(args) > notes_start else ""
            try:
                trade = self.trade_logger.record(trade_type, symbol, name, market, price, quantity, date, notes)
            except ValueError as e:
                yield event.plain_result(f"记录交易失败: {e}")
                return
            type_cn = "买入" if trade_type == "buy" else "卖出"
            yield event.plain_result(
                f"📒 已记录{type_cn}:\n"
                f"ID: `{trade['id']}`\n"
                f"标的: {trade['name']}({trade['symbol']}) · {trade['market']}\n"
                f"价格: {trade['price']:.2f} | 数量: {trade['quantity']}\n"
                f"金额: {trade['amount']:,.2f} | 日期: {trade['date']}"
            )

        elif sub == "log":
            limit = 20
            if len(args) > 1:
                try:
                    limit = int(args[1])
                except ValueError:
                    limit = 20
            limit = min(limit, 200)

            trades = self.trade_logger.list_all(limit)
            if not trades:
                yield event.plain_result("📭 暂无交易记录。")
                return

            lines = [f"## 📒 交易记录 (最近{min(limit, len(trades))}条)", ""]
            lines.append("| 日期 | 类型 | 标的 | 价格 | 数量 | 金额 |")
            lines.append("|------|------|------|------|------|------|")
            for t in trades:
                type_cn = "🟢 买入" if t["type"] == "buy" else "🔴 卖出"
                lines.append(
                    f"| {t['date']} | {type_cn} | {t['name']}({t['symbol']}) | "
                    f"{t['price']:.2f} | {t['quantity']} | {t['amount']:,.2f} |"
                )

            yield event.plain_result("\n".join(lines))

        elif sub == "summary":
            s = self.trade_logger.summary()
            if s["trade_count"] == 0:
                yield event.plain_result("📭 暂无交易记录。")
                return

            lines = [
                "## 📊 交易汇总",
                "",
                f"总交易笔数: {s['trade_count']}",
                f"总买入金额: {s['total_buy_amount']:,.2f}",
                f"总卖出金额: {s['total_sell_amount']:,.2f}",
                f"净现金流: {s['net_cash_flow']:+,.2f}",
                "",
                "### 📋 各标的已实现盈亏",
                "",
                "| 标的 | 市场 | 买入均价 | 卖出均价 | 净持仓 | 已实现盈亏 |",
                "|------|------|----------|----------|--------|------------|",
            ]
            for bs in s.get("by_symbol", []):
                pnl_str = f"{bs['realized_pnl']:+,.2f}"
                lines.append(
                    f"| {bs['name']}({bs['symbol']}) | {bs.get('market', '')} | "
                    f"{bs['avg_buy_price']:.2f} | {bs['avg_sell_price']:.2f} | "
                    f"{bs['net_qty']} | {pnl_str} |"
                )

            yield event.plain_result("\n".join(lines))

        else:
            yield event.plain_result(self._usage_trade())

    # ── LLM Tools ────────────────────────────────────────────

    @filter.llm_tool(name="query_portfolio")
    async def tool_query_portfolio(self, event: AstrMessageEvent, query_type: str = "") -> str:
        """查询当前投资组合信息。可以查看持仓概况、特定市场或行业持仓。
        Args:
            query_type(string): 查询类型，可选值: summary(概况)、market(市场分布)、industry(行业分布)、或为空表示全部信息
        """
        positions = self.pm.list_all()
        if not positions:
            return "当前投资组合为空。"

        enriched = await self.mdp.get_batch(positions)
        analysis = self.analyzer.analyze(enriched)

        if query_type == "summary" or query_type == "概况":
            return self.reporter.portfolio_summary(positions, analysis)
        elif query_type == "market" or query_type == "市场分布":
            return self.reporter.concentration_report(analysis)
        elif query_type == "industry" or query_type == "行业分布":
            return self.reporter.concentration_report(analysis)
        else:
            return self.reporter.portfolio_summary(positions, analysis)

    @filter.llm_tool(name="get_market_quote")
    async def tool_get_market_quote(self, event: AstrMessageEvent, symbol: str, market: str = "A股") -> str:
        """获取指定股票/资产的实时行情。
        Args:
            symbol(string): 资产代码，A股为6位数字，美股为英文字母代码，港股为5位数字，虚拟币为英文名如bitcoin，大宗货物为雅虎期货代码如GC=F
            market(string): 市场类型，可选值: A股、美股、港股、虚拟币、大宗货物。默认A股
        """
        quote = await self.mdp.get_quote(symbol.upper(), market)
        if not quote:
            return f"未找到 {symbol} 在 {market} 的行情数据。请确认代码和市场类型是否正确。"

        lines = [
            f"{quote['name']}({quote['symbol']}) — {quote['market']}",
            f"现价: {quote['price']:.2f} {quote.get('currency', '')}",
        ]
        if "change_pct" in quote:
            sign = "+" if quote.get("change_pct", 0) >= 0 else ""
            lines.append(f"涨跌: {sign}{quote.get('change_pct', 0):.2f}%")
        if "high" in quote:
            lines.append(f"最高: {quote['high']:.2f} | 最低: {quote['low']:.2f}")

        return "\n".join(lines)

    @filter.llm_tool(name="analyze_portfolio")
    async def tool_analyze_portfolio(self, event: AstrMessageEvent, analysis_type: str = "full") -> str:
        """分析投资组合的风险和集中度。
        Args:
            analysis_type(string): 分析类型，可选值: concentration(集中度分析)、risk(风险评估)、full(全面分析)。默认full
        """
        positions = self.pm.list_all()
        if not positions:
            return "当前投资组合为空，无法分析。"

        enriched = await self.mdp.get_batch(positions)
        analysis = self.analyzer.analyze(enriched)

        if analysis_type == "concentration":
            return self.reporter.concentration_report(analysis)
        elif analysis_type == "risk":
            return self.reporter.risk_report(analysis)
        else:
            summary = self.reporter.portfolio_summary(positions, analysis)
            conc = self.reporter.concentration_report(analysis)
            risk = self.reporter.risk_report(analysis)
            return f"{summary}\n\n{conc}\n\n{risk}"

    @filter.llm_tool(name="get_market_news")
    async def tool_get_market_news(self, event: AstrMessageEvent, market: str = "A股", limit: int = 5) -> str:
        """获取最新的市场新闻/资讯。
        Args:
            market(string): 市场类型，可选值: A股、美股。默认A股
            limit(number): 返回新闻条数，默认5条，最多10条
        """
        limit = min(limit, 10)
        news = await self.mdp.get_news(market, limit)
        if not news:
            return f"暂无 {market} 相关新闻。"

        lines = [f"### 📰 {market} 最新资讯"]
        for i, n in enumerate(news, 1):
            time_str = n.get("time", "")
            lines.append(f"{i}. {n['title']}" + (f" ({time_str})" if time_str else ""))

        return "\n".join(lines)

    @filter.llm_tool(name="smart_add_position")
    async def tool_smart_add_position(
        self, event: AstrMessageEvent, symbol_or_name: str, cost: float, quantity: float
    ) -> str:
        """智能添加投资持仓。只需提供代码/名称、成本价和数量，系统会自动识别市场、类型、行业。
        如果代码有歧义（如匹配到多个市场），会列出所有可能选项让用户选择。
        Args:
            symbol_or_name(string): 投资品代码或名称，如"600519"、"茅台"、"AAPL"、"bitcoin"、"黄金"
            cost(number): 持仓成本价（每股/每份的买入均价）
            quantity(number): 持仓数量（股数/份额）
        """
        msg = await self._resolve_and_add(str(symbol_or_name), float(cost), float(quantity))
        return msg

    @filter.llm_tool(name="set_price_alert")
    async def tool_set_price_alert(
        self, event: AstrMessageEvent, symbol: str, name: str, market: str,
        condition: str, target_value: float, notes: str = ""
    ) -> str:
        """设置价格预警，当标的价格满足条件时自动通知。
        Args:
            symbol(string): 资产代码
            name(string): 资产名称
            market(string): 市场类型，可选值: A股、美股、港股、虚拟币、大宗货物
            condition(string): 触发条件，可选值: > (高于)、< (低于)、>= (达到)、<= (跌破)、+% (涨幅超)、-% (跌幅超)
            target_value(number): 目标价格
            notes(string): 备注
        """
        try:
            alert = self.alert_mgr.add(symbol, name, market, condition, target_value, notes)
        except ValueError as e:
            return f"设置预警失败: {e}"
        return (
            f"🔔 已设置价格预警:\n"
            f"标的: {alert['name']}({alert['symbol']}) · {alert['market']}\n"
            f"条件: {alert['condition']} {alert['target_value']}\n"
            f"ID: `{alert['id']}`"
        )

    @filter.llm_tool(name="get_benchmark")
    async def tool_get_benchmark(self, event: AstrMessageEvent) -> str:
        """获取投资组合与主要市场指数的基准对比，了解组合是否跑赢大盘。"""
        positions = self.pm.list_all()
        if not positions:
            return "当前投资组合为空，无法进行基准对比。"

        enriched = await self.mdp.get_batch(positions)
        analysis = self.analyzer.analyze(enriched)
        indices = await self.mdp.get_indices()

        total_pnl_pct = analysis.get("total_pnl_pct", 0)
        lines = [
            f"## 📊 基准对比",
            f"组合收益: {total_pnl_pct:+.2f}%",
            "",
            "| 指数 | 涨跌 | 对比 |",
            "|------|------|------|",
        ]
        for idx in indices[:6]:
            idx_pct = idx.get("change_pct", 0)
            delta = total_pnl_pct - idx_pct
            beat = "✅ 跑赢" if delta > 0 else ("🔴 跑输" if delta < 0 else "➖ 持平")
            lines.append(f"| {idx['name']} | {idx_pct:+.2f}% | {beat} ({delta:+.2f}%) |")

        return "\n".join(lines)

    @filter.llm_tool(name="manage_watchlist")
    async def tool_manage_watchlist(
        self, event: AstrMessageEvent, action: str, symbol: str = "",
        name: str = "", market: str = "", notes: str = ""
    ) -> str:
        """管理自选股列表，添加/查看/删除关注标的。
        Args:
            action(string): 操作类型，可选值: add(添加)、list(查看)、remove(删除)
            symbol(string): 资产代码 (add/remove 时必填)
            name(string): 资产名称 (add 时必填)
            market(string): 市场类型 (add 时必填)
            notes(string): 备注 (add 时可选)
        """
        if action == "add":
            if not symbol or not name or not market:
                return "添加自选需要提供 symbol、name、market 参数。"
            try:
                item = self.watchlist.add(symbol, name, market, notes)
            except ValueError as e:
                return f"添加自选失败: {e}"
            return f"⭐ 已添加自选: {item['name']}({item['symbol']}) · {item['market']} (ID: `{item['id']}`)"

        elif action == "list":
            items = self.watchlist.list_all()
            if not items:
                return "自选列表为空。"
            lines = ["## ⭐ 自选列表"]
            for it in items:
                quote = await self.mdp.get_quote(it["symbol"], it["market"])
                if quote:
                    chg = quote.get("change_pct", 0)
                    chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
                    lines.append(f"- {it['name']}({it['symbol']}) · {it['market']} | {quote['price']:.2f} | {chg_str}")
                else:
                    lines.append(f"- {it['name']}({it['symbol']}) · {it['market']}")
            return "\n".join(lines)

        elif action == "remove":
            if not symbol:
                return "删除自选需要提供 symbol (自选ID)。"
            removed = self.watchlist.remove(symbol)
            if removed:
                return f"✅ 已从自选移除: {removed['name']}({removed['symbol']})"
            return f"❌ 未找到自选 ID: {symbol}"

        return f"不支持的操作: {action}。可选: add / list / remove"

    # ── Alert Checker ────────────────────────────────────────

    async def _check_alerts(self) -> None:
        """Check all active alerts against current prices and notify if triggered."""
        active = self.alert_mgr.list_active()
        if not active:
            return

        target_session = self.config.get("target_session", "")
        if not target_session:
            return

        triggered_any = []
        for alert in active:
            try:
                quote = await self.mdp.get_quote(alert["symbol"], alert["market"])
                if not quote:
                    continue
                current_price = quote.get("price", 0)
                if current_price <= 0:
                    continue

                if self.alert_mgr.check_condition(alert, current_price):
                    self.alert_mgr.mark_triggered(alert["id"])
                    triggered_any.append((alert, current_price))
            except Exception:
                continue

        if triggered_any:
            lines = ["🔔 **价格预警触发**\n"]
            for alert, price in triggered_any:
                lines.append(
                    f"- {alert['name']}({alert['symbol']}) "
                    f"现价 {price:.2f} 触发条件: {alert['condition']} {alert['target_value']}"
                )
            chain = MessageChain().message("\n".join(lines))
            await self.context.send_message(target_session, chain)

    async def _take_nav_snapshot(self) -> None:
        """Take a daily NAV snapshot for the portfolio."""
        positions = self.pm.list_all()
        if not positions:
            return

        enriched = await self.mdp.get_batch(positions)
        analysis = self.analyzer.analyze(enriched)
        indices = await self.mdp.get_indices()

        total_value = analysis.get("total_value", 0)
        if total_value <= 0:
            return

        self.nav_tracker.snapshot(
            total_value=total_value,
            positions=[
                {
                    "symbol": p.get("symbol", ""),
                    "name": p.get("name", ""),
                    "market_value": p.get("market_value") or 0,
                }
                for p in enriched
            ],
            indices=indices,
        )
        logger.info(f"NAV snapshot taken: {total_value:,.2f}")

    # ── Cron ─────────────────────────────────────────────────

    async def _setup_cron_jobs(self) -> None:
        try:
            cron = self.context.cron_manager
        except AttributeError:
            logger.warning("cron_manager not available, skipping scheduled jobs")
            return

        auto_watch = self.config.get("auto_market_watch", False)
        target_session = self.config.get("target_session", "")

        if auto_watch and target_session:
            daily_time = self.config.get("daily_report_time", "15:30")
            try:
                hour, minute = map(int, daily_time.split(":"))
            except ValueError:
                hour, minute = 15, 30

            await cron.add_basic_job(
                name="investment_daily_report",
                cron_expression=f"{minute} {hour} * * 1-5",
                handler=self._send_daily_report_to_session,
                description="投资助手每日收盘报告",
                timezone="Asia/Shanghai",
                enabled=True,
                persistent=False,
            )

            week_day = int(self.config.get("weekly_report_day", 5))
            week_time = self.config.get("weekly_report_time", "17:00")
            try:
                w_hour, w_minute = map(int, week_time.split(":"))
            except ValueError:
                w_hour, w_minute = 17, 0

            await cron.add_basic_job(
                name="investment_weekly_report",
                cron_expression=f"{w_minute} {w_hour} * * {week_day}",
                handler=self._send_weekly_report_to_session,
                description="投资助手周度报告",
                timezone="Asia/Shanghai",
                enabled=True,
                persistent=False,
            )

            month_day = int(self.config.get("monthly_report_day", 1))
            await cron.add_basic_job(
                name="investment_monthly_report",
                cron_expression=f"{w_minute} {w_hour} {month_day} * *",
                handler=self._send_monthly_report_to_session,
                description="投资助手月度报告",
                timezone="Asia/Shanghai",
                enabled=True,
                persistent=False,
            )

            logger.info("投资助手定时报告已注册")

        # NAV snapshot daily at 15:05 (after A-share close) — independent of auto_watch
        await cron.add_basic_job(
            name="investment_nav_snapshot",
            cron_expression="5 15 * * 1-5",
            handler=self._take_nav_snapshot,
            description="投资助手每日净值快照",
            timezone="Asia/Shanghai",
            enabled=True,
            persistent=False,
        )

        # Alert check every 5 minutes — needs target_session to notify
        target_session = self.config.get("target_session", "")
        if target_session:
            await cron.add_basic_job(
                name="investment_alert_check",
                cron_expression="*/5 * * * *",
                handler=self._check_alerts,
                description="投资助手价格预警检查 (每5分钟)",
                timezone="Asia/Shanghai",
                enabled=True,
                persistent=False,
            )

        logger.info("投资助手定时任务已注册 (NAV快照 + 预警检查)")

    async def _send_daily_report_to_session(self) -> None:
        target = self.config.get("target_session", "")
        if not target:
            return
        positions = self.pm.list_all()
        if not positions:
            return
        enriched = await self.mdp.get_batch(positions)
        analysis = self.analyzer.analyze(enriched)
        indices = await self.mdp.get_indices()
        report = self.reporter.daily_report(positions, analysis, indices)
        chain = MessageChain().message(report)
        await self.context.send_message(target, chain)

    async def _send_weekly_report_to_session(self) -> None:
        target = self.config.get("target_session", "")
        if not target:
            return
        positions = self.pm.list_all()
        if not positions:
            return
        enriched = await self.mdp.get_batch(positions)
        analysis = self.analyzer.analyze(enriched)
        end = datetime.now()
        start = end - timedelta(days=7)
        report = self.reporter.weekly_report(analysis, start.strftime("%m-%d"), end.strftime("%m-%d"))
        chain = MessageChain().message(report)
        await self.context.send_message(target, chain)

    async def _send_monthly_report_to_session(self) -> None:
        target = self.config.get("target_session", "")
        if not target:
            return
        positions = self.pm.list_all()
        if not positions:
            return
        enriched = await self.mdp.get_batch(positions)
        analysis = self.analyzer.analyze(enriched)
        report = self.reporter.monthly_report(analysis, datetime.now().strftime("%Y年%m月"))
        chain = MessageChain().message(report)
        await self.context.send_message(target, chain)
