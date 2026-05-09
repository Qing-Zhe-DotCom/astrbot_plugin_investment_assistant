# 投资助手 (Investment Assistant)

[![AstrBot Plugin](https://img.shields.io/badge/AstrBot-Plugin-blue)](https://github.com/AstrBotDevs/AstrBot)
[![Version](https://img.shields.io/badge/version-v0.1.0-green)]()
[![License](https://img.shields.io/badge/License-AGPL--3.0-orange)](https://www.gnu.org/licenses/agpl-3.0.html)

AstrBot 投资组合管理插件 — 一站式管理 A股、美股、港股、虚拟币、大宗货物投资组合，提供组合分析、风险评估与自然语言盯盘报告。

---

## ✨ 功能介绍

- **🧠 智能资产识别** — 只需输入代码 + 成本 + 数量，自动识别市场、名称、类型、行业；支持中文名称（如「茅台」「黄金」）
- **📊 投资组合管理** — 添加/删除/编辑持仓，覆盖 A股、美股、港股、主流虚拟币、大宗货物五大市场
- **📈 实时行情盯盘** — 多源行情数据聚合（akshare + yfinance + CoinGecko），一键查看组合实时表现
- **🔍 组合分析** — HHI 赫芬达尔集中度指数、行业/市场/类型分布、货币敞口分析
- **🛡️ 风险评估** — 单标的集中度预警、市场集中度预警、行业集中度预警，自动阈值告警
- **📋 投资报告** — 日报告、周报告、月报告，自动计算盈亏与表现排名
- **🤖 LLM 自然语言交互** — 5 个 Function Calling 工具，用自然语言添加持仓、查询行情、分析组合、获取新闻
- **⏰ 定时推送** — 支持每日收盘、每周、每月定时推送报告到指定会话
- **⚙️ WebUI 可视化配置** — 通过 AstrBot 管理面板直接配置所有参数
- **🔗 多市场覆盖** — A 股（akshare 东方财富）、美股（yfinance）、港股（akshare/yfinance）、虚拟币（CoinGecko）、大宗货物（yfinance COMEX/CME 期货）

---

## 📦 安装

### 1. 安装插件

```bash
cd AstrBot/data/plugins
git clone https://github.com/Qing-Zhe-DotCom/astrbot_plugin_investment_assistant.git
```

### 2. 安装依赖

```bash
pip install akshare yfinance httpx
```

或重启 AstrBot，插件管理器将自动安装 `requirements.txt` 中的依赖。

### 3. 启用插件

在 AstrBot WebUI → 插件管理 → 找到「投资助手」→ 点击启用/重载。

---

## 📖 指令说明

### 持仓管理

| 指令 | 说明 | 示例 |
|------|------|------|
| `/add_position` | 智能添加持仓 | `/add_position 600519 1800 100` |
| `/del_position <ID>` | 删除持仓 | `/del_position abc123def456` |
| `/edit_position <ID> <字段> <值>` | 编辑持仓 | `/edit_position abc123 quantity 200` |
| `/my_portfolio` | 查看组合概览 | `/my_portfolio` |

#### 智能添加（推荐）

只需 3 个参数，系统自动识别市场、名称、类型、行业：

```
/add_position <代码> <成本价> <数量> [备注]
```

| 示例 | 自动识别结果 |
|------|-------------|
| `/add_position 600519 1800 100` | 贵州茅台 · A股 · 股票 · 白酒 |
| `/add_position AAPL 195 50` | Apple Inc. · 美股 · 股票 · 科技 |
| `/add_position bitcoin 65000 0.5` | Bitcoin · 虚拟币 · 虚拟币 |
| `/add_position 黄金 2350 10` | 黄金(COMEX) · 大宗货物 · 商品 · 贵金属 |
| `/add_position 0700 380 300` | 腾讯控股 · 港股 · 股票 |
| `/add_position GC=F 2400 5` | 黄金(COMEX) · 大宗货物 · 商品 |

> 如果代码匹配到多个可能的资产（如 `BTC` 可能匹配多个同名代币），系统会列出所有候选让用户确认。

#### 手动添加（完整参数）

当自动识别不适用或需要精确控制时，使用完整格式：

```
/add_position <代码> <名称> <市场> <类型> <数量> <成本价> [行业] [备注]
```

| 参数 | 可选值 |
|------|--------|
| 市场 | `A股` `美股` `港股` `虚拟币` `大宗货物` |
| 类型 | `股票` `ETF` `虚拟币` `商品` |
| 行业 | 自由填写（白酒、科技、新能源、医药、贵金属……） |

#### 编辑持仓可修改字段

| 字段 | 说明 |
|------|------|
| `name` | 名称 |
| `quantity` | 数量 |
| `avg_cost` | 成本价 |
| `industry` | 行业 |
| `notes` | 备注 |

### 行情与盯盘

| 指令 | 说明 |
|------|------|
| `/market_watch` | 查看全部持仓实时行情 + 主要指数 |
| `/market_watch <代码> <市场>` | 查看单个资产行情 |
| `/market_watch AAPL 美股` | 查看 Apple 美股行情 |
| `/market_watch BTC 虚拟币` | 查看比特币行情 |
| `/market_watch 黄金 大宗货物` | 查看黄金期货行情 |

### 组合分析

| 指令 | 说明 |
|------|------|
| `/portfolio_analysis` | 全面分析（概览 + 集中度 + 风险） |
| `/portfolio_analysis concentration` | 仅集中度分析（HHI 指数 + 分布） |
| `/portfolio_analysis risk` | 仅风险评估 |

### 投资报告

| 指令 | 说明 |
|------|------|
| `/investment_report` 或 `/investment_report daily` | 日报告（当日表现 + 指数） |
| `/investment_report weekly` | 周报告（7 日表现 + 最佳/最差） |
| `/investment_report monthly` | 月报告（月全景 + 各维度分布） |

---

## 🤖 AI 自然语言使用

本插件注册了 5 个 LLM Function Calling 工具，启用后可直接用自然语言交互：

| 工具 | 功能 | 触发示例 |
|------|------|----------|
| `smart_add_position` | 智能添加持仓 | "我买了 100 股茅台，成本 1800"、"帮我记录 0.5 个比特币，买入价 65000" |
| `query_portfolio` | 查询组合 | "我的持仓怎么样？"、"投资组合表现如何？" |
| `get_market_quote` | 实时行情 | "茅台现在多少钱？"、"帮我查 AAPL 股价"、"比特币涨了没？" |
| `analyze_portfolio` | 组合分析 | "分析一下我的投资组合风险"、"组合集中度怎么样？"、"有哪些风险需要关注？" |
| `get_market_news` | 市场资讯 | "最近有什么A股新闻？"、"看看美股最新动态" |

> 💡 工具自动注册到 AstrBot 的 LLM Agent 中，AI 模型判断用户意图后自动调用对应工具。

---

## ⚙️ 配置说明

在 AstrBot WebUI → 插件管理 → 投资助手 → 配置面板中设置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `default_currency` | 默认显示货币 | CNY |
| `auto_market_watch` | 启用定时推送 | false |
| `daily_report_time` | 每日报告时间 (CST HH:MM) | 15:30 |
| `weekly_report_day` | 周报日 (1=周一 … 7=周日) | 5 (周五) |
| `weekly_report_time` | 周报推送时间 (CST HH:MM) | 17:00 |
| `monthly_report_day` | 月报日 (每月几号, 1-28) | 1 |
| `risk_warning_threshold` | 单标的风险预警阈值 (%) | 30.0 |
| `target_session` | 推送目标会话 (UMO 格式) | 空 |

> **target_session 格式**: `平台名:类型:会话ID`，例如 `aiocqhttp:group:123456789`（QQ 群）或 `aiocqhttp:private:987654321`（QQ 私聊）。

---

## 📋 使用示例

### 场景一：智能添加持仓

```
用户: /add_position 600519 1800 100
Bot:  🔍 正在识别「600519」...
      ✅ 已智能添加持仓:
      ID: 5b159e87ac18
      代码: 600519 | 名称: 贵州茅台
      市场: A股 | 类型: 股票 · 白酒
      数量: 100.0 | 成本价: 1800.0
      识别来源: a_share_code

用户: /add_position AAPL 195 50
Bot:  ✅ 已智能添加持仓:
      ID: a3f7c91d2e4b
      代码: AAPL | 名称: Apple Inc.
      市场: 美股 | 类型: 股票 · Consumer Electronics
      数量: 50.0 | 成本价: 195.0
      识别来源: us_yfinance

用户: /add_position bitcoin 65000 0.5
Bot:  ✅ 已智能添加持仓:
      代码: BTC | 名称: Bitcoin
      市场: 虚拟币 | 类型: 虚拟币
      数量: 0.5 | 成本价: 65000.0
      识别来源: coingecko
```

### 场景二：自然语言添加（LLM 对话）

```
用户: 我最近买了 200 股五粮液，平均成本 152 块
Bot:  [AI 调用 smart_add_position("五粮液", 152, 200)]
      ✅ 已智能添加持仓:
      代码: 000858 | 名称: 五粮液
      市场: A股 | 类型: 股票 · 白酒
      数量: 200.0 | 成本价: 152.0

用户: 帮我也记一下，我持有 10 手黄金期货，成本 2350
Bot:  [AI 调用 smart_add_position("黄金", 2350, 10)]
      ✅ 已智能添加持仓:
      代码: GC=F | 名称: 黄金(COMEX)
      市场: 大宗货物 | 类型: 商品 · 贵金属
```

### 场景三：查看组合与行情

```
用户: /my_portfolio
Bot:  ⏳ 正在获取实时行情...

      ## 📊 我的投资组合

      💰 总市值: 40.35万 CNY
      📊 总盈亏: 📈 1.46万 CNY (+3.74%)
      📦 持仓数量: 4

      | 代码 | 名称 | 持仓 | 成本 | 现价 | 市值 | 盈亏 | 涨幅 |
      |------|------|------|------|------|------|------|------|
      | 600519 | 贵州茅台 | 100 | 1800 | 1850 | 18.5万 | 📈 +5000 | +2.78% |
      | 000858 | 五粮液 | 200 | 152 | 158 | 3.16万 | 📈 +1200 | +3.95% |
      | AAPL | Apple Inc. | 50 | 195 | 200 | 1万 | 📈 +250 | +2.56% |
      | BTC | Bitcoin | 0.5 | 65000 | 68000 | 3.4万 | 📈 +1500 | +4.62% |
```

### 场景四：组合分析与风险

```
用户: /portfolio_analysis risk
Bot:  ⏳ 正在分析...

      ## 🛡️ 风险评估报告
      ### ⚠️ 风险预警
      - 🔴 贵州茅台(600519) 占比 45.8%，超过预警阈值 30.0%
      - 🟡 五粮液(000858) 占比 10.2%，接近预警阈值
      - ⚠️ 行业集中度偏高: 白酒 占比 56.0%
      - ⚠️ 市场集中度偏高: A股 占比 71.2%
```

### 场景五：自然语言盯盘

```
用户: 今天市场怎么样？我的持仓表现如何？
Bot:  [AI 调用 query_portfolio + get_market_quote + get_market_news]

      ## 📊 我的投资组合
      💰 总市值: 41.28万 CNY (+2.3%)
      今日涨幅最大: Bitcoin +4.62%
      今日跌幅最大: 无

      ## 📰 A股 最新资讯
      1. 沪指收涨0.8%，白酒板块领涨
      2. 北向资金今日净流入超50亿

用户: 有什么风险需要我关注的吗？
Bot:  [AI 调用 analyze_portfolio("risk")]
      当前有 3 个风险预警：
      - 贵州茅台占比 45.8%，单标的风险过高
      - 白酒行业占比 56%，行业过于集中
      - 建议考虑适当减仓茅台或增配其他行业
```

---

## 🛠️ 技术架构

```
main.py                  # 插件入口: 指令/LLM工具/定时任务
├── portfolio_manager.py # 持仓 CRUD + JSON 数据持久化
├── market_data.py       # 行情数据 + 智能资产识别
│   ├── MarketDataProvider  — 多源行情聚合 (30s 缓存)
│   │   ├── A股   → akshare (东方财富)
│   │   ├── 美股   → yfinance (Yahoo Finance)
│   │   ├── 港股   → akshare + yfinance
│   │   ├── 虚拟币 → CoinGecko API
│   │   └── 大宗货物 → yfinance (COMEX/CME 期货)
│   └── AssetResolver      — 智能资产识别引擎
│       ├── 代码/名称 → 多市场并发解析
│       ├── 置信度评分 + 歧义检测
│       └── 行业自动补全
├── analysis.py          # HHI 集中度 + 风险评估
└── report_generator.py  # 日/周/月报告 Markdown 生成
```

### 数据流

```
用户输入 "600519 1800 100"
  → cmd_add_position 检测智能格式
  → AssetResolver.resolve("600519")
    → _resolve_a_share("600519")      命中: 贵州茅台 · A股 · 股票
    → _resolve_a_share_industry()     补充: 白酒
  → portfolio_manager.add()           持久化到 JSON
  → 返回确认消息
```

---

## 📄 License

[GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.html)

Copyright (C) 2025 Qing-Zhe-DotCom

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License.

---

> 💡 **反馈与贡献**: 欢迎提交 [Issue](https://github.com/Qing-Zhe-DotCom/astrbot_plugin_investment_assistant/issues) 或 Pull Request。
