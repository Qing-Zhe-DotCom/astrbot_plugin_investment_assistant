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


class AssetResolver:
    """Resolve an asset from a code or name across all five markets.

    Returns structured matches with confidence scores so the caller can decide
    whether to auto-accept or ask the user to disambiguate.
    """

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _a_share_type(code: str) -> str:
        c = str(code)
        if len(c) == 6 and c.startswith(("51", "50", "56")):
            return "ETF"
        if len(c) == 6 and c.startswith(("15", "16", "18")):
            return "ETF"
        return "股票"

    @staticmethod
    def _hk_type(code: str) -> str:
        c = str(code).zfill(5)
        if "03000" <= c <= "03999":
            return "ETF"
        if c.startswith(("82", "83", "87", "88")):
            return "ETF"
        return "股票"

    @staticmethod
    def _commodity_group(symbol: str) -> str:
        mapping = {
            "GC": "贵金属", "SI": "贵金属", "PL": "贵金属", "PA": "贵金属",
            "CL": "能源", "BZ": "能源", "NG": "能源", "HO": "能源", "RB": "能源",
            "HG": "工业金属", "AL": "工业金属", "NI": "工业金属", "ZR": "工业金属",
            "ZC": "农产品", "ZS": "农产品", "ZW": "农产品", "ZC": "农产品",
        }
        prefix = symbol.replace("=F", "").upper()
        for key, group in mapping.items():
            if prefix.startswith(key):
                return group
        return "大宗货物"

    # ── Per-market resolvers ───────────────────────────────

    async def _resolve_a_share(self, query: str) -> list[dict]:
        try:
            import akshare as ak  # type: ignore
        except ImportError:
            return []
        try:
            df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
        except Exception as e:
            logger.warning(f"A-share resolution failed: {e}")
            return []

        results = []
        q = str(query).strip()

        # Normalise code column to str for reliable comparison
        code_series = df["代码"].astype(str).str.strip()
        name_series = df["名称"].astype(str).str.strip()

        # Exact code match (highest confidence)
        mask = code_series == q
        if mask.any():
            idx = mask.idxmax() if hasattr(mask, "idxmax") else mask[mask].index[0]
            r = df.loc[idx]
            code = str(r["代码"]).strip()
            results.append({
                "symbol": code,
                "name": str(r["名称"]).strip(),
                "market": "A股",
                "type": self._a_share_type(code),
                "industry": "",
                "confidence": 1.0,
                "source": "a_share_code",
            })
            return results

        # Exact name match (more reliable than str.contains for Chinese)
        exact_mask = name_series == q
        if exact_mask.any():
            for _, r in df[exact_mask].head(8).iterrows():
                code = str(r["代码"]).strip()
                results.append({
                    "symbol": code,
                    "name": str(r["名称"]).strip(),
                    "market": "A股",
                    "type": self._a_share_type(code),
                    "industry": "",
                    "confidence": 1.0,
                    "source": "a_share_name_exact",
                })
            results.sort(key=lambda x: x["confidence"], reverse=True)
            return results[:5]

        # Fuzzy name match (regex=False for literal substring matching)
        try:
            name_mask = name_series.str.contains(q, na=False, regex=False)
        except Exception:
            name_mask = name_series.str.contains(q, na=False)
        if name_mask.any():
            matched = df[name_mask]
            for _, r in matched.head(8).iterrows():
                code = str(r["代码"]).strip()
                name_val = str(r["名称"]).strip()
                results.append({
                    "symbol": code,
                    "name": name_val,
                    "market": "A股",
                    "type": self._a_share_type(code),
                    "industry": "",
                    "confidence": 0.7,
                    "source": "a_share_name",
                })

        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:5]

    async def _resolve_a_share_industry(self, symbol: str) -> str:
        try:
            import akshare as ak  # type: ignore
        except ImportError:
            return ""
        try:
            info = await asyncio.to_thread(
                ak.stock_individual_info_em, symbol=symbol
            )
            rows = info[info["item"] == "行业"]
            if not rows.empty:
                return str(rows["value"].iloc[0])
        except Exception:
            pass
        return ""

    async def _resolve_us_stock(self, query: str) -> list[dict]:
        try:
            import yfinance as yf  # type: ignore
        except ImportError:
            return []
        sym = str(query).strip().upper()
        if not sym.isascii() or len(sym) > 10:
            return []
        try:
            ticker = await asyncio.to_thread(lambda: yf.Ticker(sym))
            info = await asyncio.to_thread(lambda: ticker.info)
        except Exception as e:
            logger.warning(f"US stock resolution failed for {sym}: {e}")
            return []

        if not info or info.get("shortName") is None:
            return []

        qt = info.get("quoteType", "").upper()
        if qt == "ETF":
            type_ = "ETF"
        elif qt == "FUTURES":
            type_ = "商品"
        elif qt == "CRYPTOCURRENCY":
            type_ = "虚拟币"
        else:
            type_ = "股票"

        name = str(info.get("shortName") or info.get("longName") or sym)
        sector = str(info.get("sector", ""))
        industry = str(info.get("industry", sector))
        exchange = str(info.get("exchange", ""))
        currency = str(info.get("currency", "USD"))

        return [{
            "symbol": sym,
            "name": name,
            "market": "美股",
            "type": type_,
            "industry": industry,
            "confidence": 0.95,
            "source": "us_yfinance",
            "currency": currency if currency else "USD",
            "exchange": exchange,
        }]

    async def _resolve_hk_stock(self, query: str) -> list[dict]:
        try:
            import akshare as ak  # type: ignore
        except ImportError:
            return []
        try:
            df = await asyncio.to_thread(ak.stock_hk_spot_em)
        except Exception as e:
            logger.warning(f"HK resolution query failed: {e}")
            return []

        q = str(query).strip()

        # Normalise columns
        code_series = df["代码"].astype(str).str.strip()
        name_series = df["名称"].astype(str).str.strip()

        # Exact code match
        code_key = q.zfill(5)
        code_rows = df[code_series == code_key]
        if not code_rows.empty:
            r = code_rows.iloc[0]
            code = str(r["代码"])
            return [{
                "symbol": code,
                "name": str(r["名称"]),
                "market": "港股",
                "type": self._hk_type(code),
                "industry": "",
                "confidence": 1.0,
                "source": "hk_code",
            }]

        # Exact name match
        exact_mask = name_series == q
        if exact_mask.any():
            results = []
            for _, r in df[exact_mask].head(8).iterrows():
                code = str(r["代码"]).strip()
                results.append({
                    "symbol": code,
                    "name": str(r["名称"]).strip(),
                    "market": "港股",
                    "type": self._hk_type(code),
                    "industry": "",
                    "confidence": 1.0,
                    "source": "hk_name_exact",
                })
            return results[:5]

        # Fuzzy name match
        try:
            name_mask = name_series.str.contains(q, na=False, regex=False)
        except Exception:
            name_mask = name_series.str.contains(q, na=False)
        if name_mask.any():
            results = []
            for _, r in df[name_mask].head(8).iterrows():
                code = str(r["代码"]).strip()
                results.append({
                    "symbol": code,
                    "name": str(r["名称"]).strip(),
                    "market": "港股",
                    "type": self._hk_type(code),
                    "industry": "",
                    "confidence": 0.7,
                    "source": "hk_name",
                })
            return results[:5]

        return []

    async def _resolve_crypto(self, query: str) -> list[dict]:
        q = str(query).strip().lower()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.coingecko.com/api/v3/search",
                    params={"query": q},
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
        except Exception as e:
            logger.warning(f"Crypto search failed for {q}: {e}")
            return []

        coins = data.get("coins", [])
        if not coins:
            return []

        results = []
        for c in coins[:10]:
            symbol = str(c.get("symbol", "")).upper()
            cid = str(c.get("id", ""))
            name = str(c.get("name", cid))
            rank = c.get("market_cap_rank") or 99999
            exact_sym = symbol == q.upper()
            exact_name = cid.lower() == q.lower()

            if exact_sym and exact_name:
                confidence = 0.98
            elif exact_sym:
                confidence = 0.93
            elif exact_name:
                confidence = 0.90
            elif q in cid.lower() or q.lower() in cid.lower():
                confidence = 0.7
            else:
                confidence = 0.4

            # Penalise deeper matches — lower-ranked coins with same symbol
            # are less likely to be the intended target
            if rank > 100 and not (exact_sym and exact_name):
                confidence -= 0.15
            # Boost confidence for top-ranked well-known coins
            if rank <= 10:
                confidence = min(1.0, confidence + 0.05)

            results.append({
                "symbol": symbol,
                "name": name,
                "market": "虚拟币",
                "type": "虚拟币",
                "industry": "",
                "confidence": confidence,
                "source": "coingecko",
                "rank": rank,
            })

        results.sort(key=lambda x: (x["confidence"], -x.get("rank", 99999)), reverse=True)
        return results[:5]

    async def _resolve_commodity(self, query: str) -> list[dict]:
        sym = str(query).strip().upper()
        # Handle common Chinese names
        name_map = {
            "黄金": "GC=F", "白银": "SI=F", "铜": "HG=F",
            "原油": "CL=F", "天然气": "NG=F", "玉米": "ZC=F",
            "大豆": "ZS=F", "布伦特": "BZ=F",
        }
        if sym in name_map:
            sym = name_map[sym]
        if not sym.endswith("=F"):
            sym = sym + "=F"

        mapping = MarketDataProvider.COMMODITY_MAP
        name = mapping.get(sym, "")
        if name:
            return [{
                "symbol": sym,
                "name": name,
                "market": "大宗货物",
                "type": "商品",
                "industry": self._commodity_group(sym),
                "confidence": 1.0 if sym in mapping else 0.6,
                "source": "commodity_map",
            }]

        # Try yfinance
        try:
            import yfinance as yf  # type: ignore
        except ImportError:
            return []
        try:
            ticker = await asyncio.to_thread(lambda: yf.Ticker(sym))
            info = await asyncio.to_thread(lambda: ticker.info)
        except Exception:
            return []
        if info and info.get("quoteType", "").upper() == "FUTURES":
            return [{
                "symbol": sym,
                "name": str(info.get("shortName", sym)),
                "market": "大宗货物",
                "type": "商品",
                "industry": self._commodity_group(sym),
                "confidence": 0.9,
                "source": "yfinance_futures",
            }]
        return []

    # ── Main resolve ───────────────────────────────────────

    async def resolve(self, query: str) -> dict[str, Any]:
        """Resolve a symbol/name across all markets.

        Returns:
            {
                'resolved': bool,
                'matches': list[dict],
                'best_match': dict | None,
                'ambiguity': 'none' | 'low' | 'high',
                'suggestion': str,
            }
        """
        q = str(query).strip()
        if not q:
            return self._empty_result("请输入投资品代码或名称。")

        # Determine which markets to probe based on query shape
        is_numeric = q.isdigit() or (q.replace(".", "").isdigit() and q.count(".") <= 1)
        is_chinese = any("一" <= c <= "鿿" for c in q)
        is_alpha = q.replace("-", "").replace(".", "").replace("_", "").isascii() and not is_numeric

        all_matches: list[dict] = []

        if is_numeric:
            # Could be A-share code or HK code
            all_matches.extend(await self._resolve_a_share(q))
            if len(q) <= 5:
                all_matches.extend(await self._resolve_hk_stock(q))
        elif is_chinese:
            # Chinese name — could be A-share, HK stock, or commodity
            all_matches.extend(await self._resolve_a_share(q))
            all_matches.extend(await self._resolve_hk_stock(q))
            all_matches.extend(await self._resolve_commodity(q))
        elif is_alpha:
            # Alpha — could be US stock, crypto, or commodity ticker
            all_matches.extend(await self._resolve_us_stock(q))
            all_matches.extend(await self._resolve_crypto(q))
            if q.upper().endswith("=F") or len(q) <= 5:
                all_matches.extend(await self._resolve_commodity(q))
        else:
            # Mixed — try everything
            all_matches.extend(await self._resolve_a_share(q))
            all_matches.extend(await self._resolve_us_stock(q))
            all_matches.extend(await self._resolve_hk_stock(q))
            all_matches.extend(await self._resolve_crypto(q))
            all_matches.extend(await self._resolve_commodity(q))

        if not all_matches:
            return self._empty_result(
                f"未找到与「{q}」匹配的资产。请检查代码/名称是否正确。\n"
                "支持的格式: A股代码(6位数字)、美股代码(如AAPL)、港股代码(5位数字)、"
                "虚拟币名称(如bitcoin)、大宗货物代码(如GC=F)"
            )

        # Deduplicate by symbol (keep highest confidence)
        seen: set[str] = set()
        deduped = []
        for m in sorted(all_matches, key=lambda x: x["confidence"], reverse=True):
            key = f"{m['market']}:{m['symbol']}"
            if key not in seen:
                seen.add(key)
                deduped.append(m)

        # Determine ambiguity level
        best = deduped[0]
        if len(deduped) == 1:
            ambiguity = "none"
            suggestion = f"✅ 已自动识别: {best['name']}({best['symbol']}) — {best['market']} · {best['type']}"
        else:
            gap = best["confidence"] - deduped[1]["confidence"]
            best_rank = best.get("rank", 99999)
            second_rank = deduped[1].get("rank", 99999)

            # Auto-accept if best has very high confidence AND either
            # (a) second is much lower confidence, or
            # (b) best is a top-50 market cap coin (well-known) with moderate gap
            if best["confidence"] >= 0.95 and (
                gap > 0.25
                or (best_rank <= 50 and gap > 0.15)
            ):
                ambiguity = "low"
                suggestion = f"✅ 已自动识别: {best['name']}({best['symbol']}) — {best['market']} · {best['type']}"
            elif best["confidence"] >= 0.90 and gap > 0.4:
                ambiguity = "low"
                suggestion = f"✅ 已自动识别: {best['name']}({best['symbol']}) — {best['market']} · {best['type']}"
            else:
                ambiguity = "high"
                suggestion = f"⚠️ 找到 {len(deduped)} 个可能的匹配，请确认:\n"
                for i, m in enumerate(deduped[:5], 1):
                    suggestion += (
                        f"{i}. {m['name']}({m['symbol']}) — "
                        f"{m['market']} · {m['type']}"
                    )
                    if m.get("industry"):
                        suggestion += f" · {m['industry']}"
                    suggestion += f" (置信度: {m['confidence']:.0%})\n"

        return {
            "resolved": True,
            "matches": deduped,
            "best_match": best if ambiguity in ("none", "low") else None,
            "ambiguity": ambiguity,
            "suggestion": suggestion,
            "query": q,
        }

    @staticmethod
    def _empty_result(msg: str) -> dict[str, Any]:
        return {
            "resolved": False,
            "matches": [],
            "best_match": None,
            "ambiguity": "high",
            "suggestion": msg,
        }
