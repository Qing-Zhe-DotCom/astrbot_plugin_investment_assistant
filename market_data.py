import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("astrbot")

A_SHARE_INDEX_MAP = {
    "上证指数": "1.000001",
    "深证成指": "0.399001",
    "创业板指": "0.399006",
    "科创50": "1.000688",
    "沪深300": "1.000300",
    "中证500": "1.000905",
}


class MarketDataProvider:
    """Multi-source market data provider with in-memory cache."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl = 30

    def _cached(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, val = entry
        if time.time() - ts > self._cache_ttl:
            del self._cache[key]
            return None
        return val

    def _set_cache(self, key: str, val: Any) -> None:
        self._cache[key] = (time.time(), val)

    # ── A-Share ──────────────────────────────────────────────

    async def get_a_share_quote(self, symbol: str) -> dict[str, Any] | None:
        cache_key = f"a_{symbol}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached
        try:
            import akshare as ak  # type: ignore
        except ImportError:
            logger.error("akshare not installed")
            return None

        try:
            df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
            row = df[df["代码"] == symbol]
            if row.empty:
                return None
            r = row.iloc[0]
            result = {
                "symbol": symbol,
                "name": r["名称"],
                "price": float(r["最新价"]),
                "change_pct": float(r["涨跌幅"]),
                "change_amount": float(r["涨跌额"]),
                "volume": float(r["成交量"]),
                "amount": float(r["成交额"]),
                "high": float(r["最高"]),
                "low": float(r["最低"]),
                "open": float(r["今开"]),
                "pre_close": float(r["昨收"]),
                "market": "A股",
                "currency": "CNY",
            }
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取A股 {symbol} 行情失败: {e}")
            return None

    async def get_a_index(self) -> list[dict[str, Any]]:
        cache_key = "a_index"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached
        try:
            import akshare as ak  # type: ignore
        except ImportError:
            return []
        try:
            df = await asyncio.to_thread(ak.stock_zh_index_spot_em)
            result = []
            for _, r in df.iterrows():
                code = str(r["代码"])
                result.append({
                    "code": code,
                    "name": r["名称"],
                    "price": float(r["最新价"]),
                    "change_pct": float(r["涨跌幅"]),
                    "change_amount": float(r["涨跌额"]),
                })
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取A股指数失败: {e}")
            return []

    # ── US Stock ─────────────────────────────────────────────

    async def get_us_quote(self, symbol: str) -> dict[str, Any] | None:
        cache_key = f"us_{symbol}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached
        try:
            import yfinance as yf  # type: ignore
        except ImportError:
            logger.error("yfinance not installed")
            return None
        try:
            ticker = await asyncio.to_thread(lambda: yf.Ticker(symbol))
            info = await asyncio.to_thread(lambda: ticker.info)
            if not info or "currentPrice" not in info:
                return None
            result = {
                "symbol": symbol,
                "name": info.get("shortName", info.get("longName", symbol)),
                "price": float(info["currentPrice"]),
                "change_pct": float(info.get("regularMarketChangePercent", 0)),
                "change_amount": float(info.get("regularMarketChange", 0)),
                "high": float(info.get("dayHigh", 0)),
                "low": float(info.get("dayLow", 0)),
                "open": float(info.get("regularMarketOpen", 0)),
                "pre_close": float(info.get("previousClose", 0)),
                "volume": int(info.get("volume", 0)),
                "market_cap": info.get("marketCap"),
                "market": "美股",
                "currency": "USD",
            }
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取美股 {symbol} 行情失败: {e}")
            return None

    # ── HK Stock ─────────────────────────────────────────────

    async def get_hk_quote(self, symbol: str) -> dict[str, Any] | None:
        cache_key = f"hk_{symbol}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached
        try:
            import akshare as ak  # type: ignore
        except ImportError:
            logger.error("akshare not installed")
            return None
        try:
            df = await asyncio.to_thread(ak.stock_hk_spot_em)
            row = df[df["代码"] == symbol]
            if row.empty:
                return None
            r = row.iloc[0]
            result = {
                "symbol": symbol,
                "name": r["名称"],
                "price": float(r["最新价"]),
                "change_pct": float(r["涨跌幅"]),
                "high": float(r["最高"]),
                "low": float(r["最低"]),
                "open": float(r["今开"]),
                "pre_close": float(r["昨收"]),
                "market": "港股",
                "currency": "HKD",
            }
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取港股 {symbol} 行情失败: {e}")
            return None

    # ── Crypto ───────────────────────────────────────────────

    async def get_crypto_quote(self, symbol: str) -> dict[str, Any] | None:
        cache_key = f"crypto_{symbol}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached
        coin_id = symbol.lower()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={
                        "ids": coin_id,
                        "vs_currencies": "usd",
                        "include_24hr_change": "true",
                        "include_24hr_vol": "true",
                    },
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                if coin_id not in data:
                    return None
                d = data[coin_id]
                result = {
                    "symbol": symbol,
                    "name": symbol,
                    "price": float(d.get("usd", 0)),
                    "change_pct": float(d.get("usd_24h_change", 0)),
                    "volume_24h": float(d.get("usd_24h_vol", 0)),
                    "market": "虚拟币",
                    "currency": "USD",
                }
                self._set_cache(cache_key, result)
                return result
        except Exception as e:
            logger.warning(f"获取加密货币 {symbol} 行情失败: {e}")
            return None

    # ── Commodity ────────────────────────────────────────────

    COMMODITY_MAP = {
        "GC=F": "黄金(COMEX)",
        "CL=F": "WTI原油",
        "BZ=F": "布伦特原油",
        "SI=F": "白银(COMEX)",
        "HG=F": "铜(COMEX)",
        "NG=F": "天然气",
        "ZC=F": "玉米",
        "ZS=F": "大豆",
    }

    async def get_commodity_quote(self, symbol: str) -> dict[str, Any] | None:
        cache_key = f"comm_{symbol}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached
        try:
            import yfinance as yf  # type: ignore
        except ImportError:
            logger.error("yfinance not installed")
            return None
        try:
            ticker = await asyncio.to_thread(lambda: yf.Ticker(symbol))
            info = await asyncio.to_thread(lambda: ticker.info)
            if not info or "currentPrice" not in info:
                return None
            result = {
                "symbol": symbol,
                "name": info.get("shortName", self.COMMODITY_MAP.get(symbol, symbol)),
                "price": float(info["currentPrice"]),
                "change_pct": float(info.get("regularMarketChangePercent", 0)),
                "high": float(info.get("dayHigh", 0)),
                "low": float(info.get("dayLow", 0)),
                "pre_close": float(info.get("previousClose", 0)),
                "market": "大宗货物",
                "currency": "USD",
            }
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"获取大宗货物 {symbol} 行情失败: {e}")
            return None

    # ── Dispatcher ───────────────────────────────────────────

    async def get_quote(self, symbol: str, market: str) -> dict[str, Any] | None:
        if market == "A股":
            return await self.get_a_share_quote(symbol)
        elif market == "美股":
            return await self.get_us_quote(symbol)
        elif market == "港股":
            return await self.get_hk_quote(symbol)
        elif market == "虚拟币":
            return await self.get_crypto_quote(symbol)
        elif market == "大宗货物":
            return await self.get_commodity_quote(symbol)
        return None

    async def get_batch(self, positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for pos in positions:
            quote = await self.get_quote(pos["symbol"], pos["market"])
            if quote:
                combined = {**pos, "current_price": quote["price"], "change_pct": quote.get("change_pct", 0)}
                combined["market_value"] = combined["current_price"] * pos["quantity"]
                combined["pnl"] = (combined["current_price"] - pos["avg_cost"]) * pos["quantity"]
                combined["pnl_pct"] = (
                    (combined["current_price"] - pos["avg_cost"]) / pos["avg_cost"] * 100
                    if pos["avg_cost"] > 0 else 0
                )
                results.append(combined)
            else:
                results.append(pos)
        return results

    # ── News ─────────────────────────────────────────────────

    async def get_a_share_news(self, limit: int = 5) -> list[dict[str, str]]:
        cache_key = "news_a"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached[:limit]
        try:
            import akshare as ak  # type: ignore
        except ImportError:
            return []
        try:
            df = await asyncio.to_thread(ak.stock_info_global_em)
            items = []
            for _, r in df.head(limit).iterrows():
                items.append({"title": str(r["标题"]), "time": str(r.get("发布时间", ""))})
            self._set_cache(cache_key, items)
            return items
        except Exception as e:
            logger.warning(f"获取A股新闻失败: {e}")
            return []

    async def get_us_news(self, limit: int = 5) -> list[dict[str, str]]:
        cache_key = "news_us"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached[:limit]
        try:
            import akshare as ak  # type: ignore
        except ImportError:
            return []
        try:
            df = await asyncio.to_thread(ak.stock_info_global_em)
            items = []
            for _, r in df.head(limit).iterrows():
                items.append({"title": str(r["标题"]), "time": str(r.get("发布时间", ""))})
            self._set_cache(cache_key, items)
            return items
        except Exception:
            return []

    async def get_news(self, market: str, limit: int = 5) -> list[dict[str, str]]:
        if market == "A股":
            return await self.get_a_share_news(limit)
        elif market == "美股":
            return await self.get_us_news(limit)
        return []

    # ── Index ────────────────────────────────────────────────

    async def get_indices(self) -> list[dict[str, Any]]:
        return await self.get_a_index()
