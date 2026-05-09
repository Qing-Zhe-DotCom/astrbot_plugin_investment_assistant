import asyncio
import logging
from datetime import datetime
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent, MessageChain, MessageEventResult
from astrbot.api.star import Context, Star, StarTools
from astrbot.api import AstrBotConfig, logger

from .portfolio_manager import PortfolioManager
from .market_data import MarketDataProvider
from .analysis import PortfolioAnalyzer
from .report_generator import ReportGenerator


class InvestmentAssistant(Star):
    """投资助手插件 — 组合管理 / 分析 / 盯盘报告"""

    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config

        data_dir = StarTools.get_data_dir()
        self.pm = PortfolioManager(data_dir)
        self.mdp = MarketDataProvider()
        risk_threshold = float(config.get("risk_warning_threshold", 30.0))
        self.analyzer = PortfolioAnalyzer(risk_threshold=risk_threshold)
        self.reporter = ReportGenerator()

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
            "用法: `/add_position <代码> <名称> <市场> <类型> <数量> <成本价> [行业] [备注]`\n"
            "市场: A股 | 美股 | 港股 | 虚拟币 | 大宗货物\n"
            "类型: 股票 | ETF | 虚拟币 | 商品\n"
            "例: `/add_position 600519 贵州茅台 A股 股票 100 1800 白酒`\n"
            "例: `/add_position BTC 比特币 虚拟币 虚拟币 0.5 65000`\n"
            "例: `/add_position GC=F 黄金 大宗货物 商品 10 2350 贵金属`"
        )

    def _usage_edit(self) -> str:
        return "用法: `/edit_position <ID> <字段> <值>`\n字段: name | quantity | avg_cost | industry | notes"

    # ── Commands ─────────────────────────────────────────────

    @filter.command("add_position")
    async def cmd_add_position(self, event: AstrMessageEvent) -> MessageEventResult:
        """添加投资持仓到组合"""
        text = event.message_str.strip()
        parts = text.split()
        if len(parts) < 7:
            yield event.plain_result(self._usage_add())
            return

        cmd = parts[0]
        args = text[len(cmd):].strip().split()
        if len(args) < 6:
            yield event.plain_result(f"参数不足。{self._usage_add()}")
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
            from datetime import timedelta
            end = datetime.now()
            start = end - timedelta(days=7)
            report = self.reporter.weekly_report(analysis, start.strftime("%m-%d"), end.strftime("%m-%d"))
        elif report_type == "monthly" or report_type == "月报":
            report = self.reporter.monthly_report(analysis, datetime.now().strftime("%Y年%m月"))
        else:
            report = self.reporter.daily_report(positions, analysis, indices)

        yield event.plain_result(report)

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

            logger.info("投资助手定时任务已注册")

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
        from datetime import timedelta
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
