# 投资助手 (Investment Assistant)

[![AstrBot Plugin](https://img.shields.io/badge/AstrBot-Plugin-blue)](https://github.com/AstrBotDevs/AstrBot)
[![Version](https://img.shields.io/badge/version-v0.1.0-green)]()

AstrBot 投资组合管理插件 — 一站式管理你的 A股、美股、港股、虚拟币、大宗货物投资组合，提供组合分析、风险评估与自然语言盯盘报告。

---

## ✨ 功能介绍

- **📊 投资组合管理** — 添加/删除/编辑持仓，覆盖 A股、美股、港股、主流虚拟币、大宗货物五大市场
- **📈 实时行情盯盘** — 多源行情数据聚合（akshare + yfinance + CoinGecko），一键查看组合实时表现
- **🔍 组合分析** — HHI 赫芬达尔集中度指数、行业/市场/类型分布、货币敞口分析
- **🛡️ 风险评估** — 单标的集中度预警、市场集中度预警、行业集中度预警
- **📋 投资报告** — 日报告、周报告、月报告，自动计算盈亏与表现排名
- **🤖 LLM 自然语言交互** — 通过 Function Calling 实现自然语言查询组合、行情、新闻
- **⏰ 定时推送** — 支持每日收盘、每周、每月定时推送报告到指定会话
- **⚙️ WebUI 可视化配置** — 通过 AstrBot 管理面板直接配置所有参数

---

## 📦 安装

### 1. 安装插件

将本仓库克隆到 AstrBot 的插件目录：

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
| `/add_position` | 添加持仓 | `/add_position 600519 贵州茅台 A股 股票 100 1800 白酒` |
| `/del_position <ID>` | 删除持仓 | `/del_position abc123def456` |
| `/edit_position <ID> <字段> <值>` | 编辑持仓 | `/edit_position abc123  quantity 200` |
| `/my_portfolio` | 查看组合概览 | `/my_portfolio` |

#### 添加持仓参数说明

```
/add_position <代码> <名称> <市场> <类型> <数量> <成本价> [行业] [备注]
```

- **代码**: 资产代码。A股为 6 位数字、美股为字母代码、港股为 5 位数字、虚拟币为英文名(如 bitcoin)、大宗货物为雅虎期货代码(如 GC=F)
- **市场**: `A股` | `美股` | `港股` | `虚拟币` | `大宗货物`
- **类型**: `股票` | `ETF` | `虚拟币` | `商品`
- **数量**: 持有数量（股/份/个）
- **成本价**: 平均成本单价
- **行业** (可选): 如 白酒、科技、新能源、医药、贵金属
- **备注** (可选): 任意文字备注

#### 编辑持仓可修改字段

| 字段 | 说明 |
|------|------|
| `name` | 名称 |
| `quantity` | 数量 |
| `avg_cost` | 成本价 |
| `industry` | 行业 |
| `notes` | 备注 |

### 行情与盯盘

| 指令 | 说明 | 示例 |
|------|------|------|
| `/market_watch` | 查看全部持仓实时行情 | `/market_watch` |
| `/market_watch <代码> <市场>` | 查看单个资产行情 | `/market_watch AAPL 美股` |
| `/market_watch BTC 虚拟币` | 查看比特币行情 | `/market_watch BTC 虚拟币` |
| `/market_watch GC=F 大宗货物` | 查看黄金期货 | `/market_watch GC=F 大宗货物` |

### 组合分析

| 指令 | 说明 | 示例 |
|------|------|------|
| `/portfolio_analysis` | 全面分析（概览+集中度+风险） | `/portfolio_analysis` |
| `/portfolio_analysis concentration` | 仅集中度分析 | `/portfolio_analysis concentration` |
| `/portfolio_analysis risk` | 仅风险评估 | `/portfolio_analysis risk` |

### 投资报告

| 指令 | 说明 | 示例 |
|------|------|------|
| `/investment_report` | 生成日报告 | `/investment_report` |
| `/investment_report daily` | 生成日报告 | `/investment_report daily` |
| `/investment_report weekly` | 生成周报告 | `/investment_report weekly` |
| `/investment_report monthly` | 生成月报告 | `/investment_report monthly` |

---

## 🤖 AI 自然语言使用

本插件注册了 4 个 LLM Function Calling 工具，启用后可直接用自然语言与 AstrBot 交互：

| 工具 | 触发示例 |
|------|----------|
| `query_portfolio` | "我的持仓怎么样？"、"帮我看看投资组合" |
| `get_market_quote` | "茅台现在多少钱？"、"帮我查一下 AAPL 股价" |
| `analyze_portfolio` | "分析一下我的投资组合风险"、"组合集中度怎么样？" |
| `get_market_news` | "最近有什么A股新闻？"、"看看美股资讯" |

> 💡 这些工具自动注册到 AstrBot 的 LLM Agent 中。当 AI 模型判断用户意图匹配工具时，会自动调用对应工具并返回结果。

---

## ⚙️ 配置说明

在 AstrBot WebUI → 插件管理 → 投资助手 → 配置面板中可设置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `default_currency` | 默认显示货币 | CNY |
| `auto_market_watch` | 启用定时推送 | false |
| `daily_report_time` | 每日报告时间 (HH:MM) | 15:30 |
| `weekly_report_day` | 周报日 (1=周一, 7=周日) | 5 (周五) |
| `weekly_report_time` | 周报推送时间 | 17:00 |
| `monthly_report_day` | 月报日 (几号) | 1 |
| `risk_warning_threshold` | 单标的风险预警阈值 (%) | 30.0 |
| `target_session` | 推送目标会话 (UMO格式) | 空 |

> **target_session 格式**: `平台名:类型:会话ID`，例如 `aiocqhttp:group:123456789`（QQ群）或 `aiocqhttp:private:987654321`（QQ私聊）。可通过在目标会话中发送任意消息后从日志获取。

---

## 📋 使用示例

### 场景一：构建投资组合

```
用户: /add_position 600519 贵州茅台 A股 股票 100 1800 白酒
Bot:  ✅ 已添加持仓:
      ID: 5b159e87ac18
      代码: 600519
      名称: 贵州茅台
      市场: A股 | 类型: 股票
      数量: 100.0 | 成本: 1800.0
      行业: 白酒

用户: /add_position AAPL Apple 美股 股票 50 180 科技
Bot:  ✅ 已添加持仓: ...

用户: /add_position BTC Bitcoin 虚拟币 虚拟币 0.5 65000
Bot:  ✅ 已添加持仓: ...

用户: /add_position GC=F 黄金期货 大宗货物 商品 10 2350 贵金属
Bot:  ✅ 已添加持仓: ...
```

### 场景二：查看组合与行情

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
      ...
```

### 场景三：组合分析

```
用户: /portfolio_analysis
Bot:  ⏳ 正在分析...
      
      ## 📈 组合集中度分析
      ### 🌍 市场分布
      集中度指数(HHI): 3860.8 — 高度集中 🔴
      - A股: 71.2%
      - 美股: 24.1%
      - 虚拟币: 2.5%
      - 大宗货物: 2.2%
      
      ### 🏭 行业分布
      - 白酒: 53.5%
      - 科技: 35.1%
      ...
      
      ## 🛡️ 风险评估报告
      ### ⚠️ 风险预警
      - 🔴 贵州茅台(600519) 占比 45.8%，超过预警阈值 30.0%
      - ⚠️ 行业集中度偏高: 白酒 占比 53.5%
```

### 场景四：自然语言交互

```
用户: 帮我看看我的投资组合表现怎么样
Bot:  [AI 自动调用 query_portfolio 工具]
      ## 📊 我的投资组合
      💰 总市值: 40.35万 CNY
      📊 总盈亏: 📈 1.46万 CNY (+3.74%)
      ...

用户: 茅台和腾讯现在什么价格？
Bot:  [AI 自动调用 get_market_quote]
      贵州茅台(600519) — A股
      现价: 1850.00 CNY
      涨跌: +2.78%
      ...

用户: 我的组合有什么风险吗？
Bot:  [AI 自动调用 analyze_portfolio]
      ## 🛡️ 风险评估报告
      🔴 贵州茅台(600519) 占比 45.8%，建议适当分散...
```

---

## 🛠️ 技术架构

```
main.py                  # 插件入口: 指令注册、LLM工具、定时任务
├── portfolio_manager.py # 持仓 CRUD + JSON 持久化
├── market_data.py       # 多源行情聚合 (30s 缓存)
│   ├── A股 → akshare (东方财富)
│   ├── 美股 → yfinance (Yahoo Finance)
│   ├── 港股 → akshare + yfinance
│   ├── 虚拟币 → CoinGecko API
│   └── 大宗货物 → yfinance (期货)
├── analysis.py          # HHI 集中度 + 风险评估
└── report_generator.py  # 日/周/月报告生成
```

## 📄 License

MIT

---

> 💡 **反馈与贡献**: 欢迎提交 [Issue](https://github.com/Qing-Zhe-DotCom/astrbot_plugin_investment_assistant/issues) 或 Pull Request。
