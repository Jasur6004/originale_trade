# -*- coding: utf-8 -*-
"""
Клиент Pocket Option через библиотеку pocketoptionapi-async.
Даёт реальные котировки и свечи для точных сигналов.
Установка: pip install pocketoptionapi-async
"""

import asyncio
import json
import re
from typing import Dict, List, Optional, Any

import config

try:
    from pocketoptionapi_async import AsyncPocketOptionClient  # type: ignore[import-untyped]
except ImportError:
    AsyncPocketOptionClient = None


def _normalize_ssid(ssid: str) -> str:
    """
    Приводит SSID к формату библиотеки: session, isDemo, uid, platform.
    Если в браузере пришёл sessionToken — подставляем его как session.
    """
    ssid = ssid.strip()
    if '"session"' in ssid and '"isDemo"' in ssid:
        return ssid
    # Ищем JSON-объект внутри 42["auth",{...}]
    match = re.search(r'42\["auth",\s*(\{.+\})\s*\]', ssid, re.DOTALL)
    if not match:
        return ssid
    try:
        data = json.loads(match.group(1))
        session = data.get("session") or data.get("sessionToken", "")
        uid = data.get("uid")
        if isinstance(uid, str):
            uid = int(uid) if uid.isdigit() else 0
        uid = uid if uid is not None else 0
        is_demo = 1 if config.POCKET_OPTION_IS_DEMO else 0
        normalized = json.dumps({
            "session": session,
            "isDemo": is_demo,
            "uid": uid,
            "platform": 1,
        })
        return f'42["auth",{normalized}]'
    except (json.JSONDecodeError, KeyError):
        return ssid


def _compute_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """RSI по последним ценам закрытия."""
    if not closes or len(closes) < period + 1:
        return None
    closes = closes[-(period + 1):]
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(ch if ch >= 0 else 0.0)
        losses.append(-ch if ch < 0 else 0.0)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


class PocketOptionClient:
    """
    Обёртка над pocketoptionapi-async для получения котировок и свечей.
    Цена и RSI берутся из последних свечей 1m.
    """

    def __init__(self):
        self._client: Optional[AsyncPocketOptionClient] = None
        self._connected = False
        self._connect_lock = asyncio.Lock()

    @property
    def is_available(self) -> bool:
        return (
            config.USE_POCKET_OPTION_API
            and bool(config.POCKET_OPTION_SSID.strip())
            and AsyncPocketOptionClient is not None
        )

    def _pair_to_asset(self, pair: str) -> Optional[str]:
        """Пару (EUR/USD или GBP/USD - OTC) в символ актива Pocket Option."""
        key = pair.replace(" - OTC", "").strip()
        asset = config.POCKET_OPTION_ASSET_IDS.get(key)
        if asset:
            return asset
        # Fallback: EUR/USD -> EURUSD, с OTC -> EURUSD_otc
        base = key.replace("/", "")
        if "OTC" in pair:
            return f"{base}_otc"
        return base

    async def _ensure_connected(self) -> bool:
        if self._connected and self._client:
            return True
        async with self._connect_lock:
            if self._connected and self._client:
                return True
            if not self.is_available:
                return False
            try:
                ssid = _normalize_ssid(config.POCKET_OPTION_SSID)
                self._client = AsyncPocketOptionClient(
                    ssid,
                    is_demo=config.POCKET_OPTION_IS_DEMO,
                    enable_logging=False,
                )
                await self._client.connect()
                self._connected = True
                return True
            except Exception as e:
                print(f"[PocketOption] Ошибка подключения: {e}")
                return False

    async def get_quote(self, pair: str, is_otc: bool = False) -> Optional[Dict[str, Any]]:
        """
        Текущая цена и RSI по паре из свечей 1m.
        Возвращает {"price": float, "rsi": float | None} или None.
        """
        if not self.is_available:
            return None
        asset = self._pair_to_asset(pair)
        if not asset:
            return None
        if not await self._ensure_connected():
            return None
        try:
            # Свечи 1 минута, 100 штук (достаточно для RSI 14)
            candles = await self._client.get_candles(asset, 60, count=100)
            if not candles:
                return None
            # Candle — объект с атрибутами open, high, low, close
            closes = []
            for c in candles:
                close = getattr(c, "close", None)
                if close is not None:
                    closes.append(float(close))
            if not closes:
                return None
            price = closes[-1]
            rsi = _compute_rsi(closes, 14) if len(closes) >= 15 else None
            return {"price": price, "rsi": rsi}
        except Exception as e:
            print(f"[PocketOption] get_quote {pair}: {e}")
            return None

    async def get_candles(self, pair: str, timeframe_min: int, count: int = 50) -> List[Dict]:
        """Последние свечи OHLC. timeframe_min: 1, 3 или 5."""
        if not self.is_available or not await self._ensure_connected():
            return []
        asset = self._pair_to_asset(pair)
        if not asset:
            return []
        try:
            period_sec = timeframe_min * 60
            candles = await self._client.get_candles(asset, period_sec, count=count)
            out = []
            for c in candles:
                out.append({
                    "open": getattr(c, "open", None),
                    "high": getattr(c, "high", None),
                    "low": getattr(c, "low", None),
                    "close": getattr(c, "close", None),
                    "time": getattr(c, "time", None),
                })
            return out
        except Exception as e:
            print(f"[PocketOption] get_candles {pair}: {e}")
            return []

    async def disconnect(self) -> None:
        self._connected = False
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None


_client: Optional[PocketOptionClient] = None


def get_pocket_option_client() -> Optional[PocketOptionClient]:
    global _client
    if _client is None:
        _client = PocketOptionClient()
    return _client if _client.is_available else None
