"""
DEX Scanner Module for Base L2.
Queries GeckoTerminal API v2 for real-time DEX intelligence on Base:
- Trending pools and volume breakouts across Aerodrome, Uniswap v3, SushiSwap, etc.
- Newly deployed liquidity pools seconds after creation.
- Token market metrics, FDV, reserves, and price velocity.
Specification: https://api.geckoterminal.com/api/v2
Zero API keys required.
"""
import time
import json
import urllib.request
from typing import Dict, Any, List, Optional

GECKOTERMINAL_BASE_URL = "https://api.geckoterminal.com/api/v2/networks/base"
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutonomousMicroEntrepreneur/1.0",
    "Accept": "application/json;version=20230203"
}

def query_geckoterminal(endpoint: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    url = f"{GECKOTERMINAL_BASE_URL}/{endpoint}"
    req = urllib.request.Request(url, headers=API_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception:
        return None

def get_base_trending_pools(min_liquidity_usd: float = 50_000.0, limit: int = 10) -> List[Dict[str, Any]]:
    """Obtiene los pools en tendencia en Base L2 con filtros de seguridad de liquidez mínima"""
    raw = query_geckoterminal("trending_pools")
    if not raw or "data" not in raw:
        return []

    pools = []
    for item in raw.get("data", []):
        attrs = item.get("attributes", {})
        reserve = float(attrs.get("reserve_in_usd", 0) or 0)
        if reserve < min_liquidity_usd:
            continue

        vol = attrs.get("volume_usd", {})
        changes = attrs.get("price_change_percentage", {})

        pools.append({
            "name": attrs.get("name"),
            "pool_address": attrs.get("address"),
            "base_token_price_usd": float(attrs.get("base_token_price_usd", 0) or 0),
            "reserve_in_usd": round(reserve, 2),
            "volume_24h_usd": round(float(vol.get("h24", 0) or 0), 2),
            "volume_1h_usd": round(float(vol.get("h1", 0) or 0), 2),
            "price_change_24h_pct": float(changes.get("h24", 0) or 0),
            "price_change_1h_pct": float(changes.get("h1", 0) or 0),
            "fdv_usd": float(attrs.get("fdv_usd", 0) or 0),
            "pool_created_at": attrs.get("pool_created_at")
        })

    return pools[:limit]

def get_base_new_pools(min_liquidity_usd: float = 1_000.0, limit: int = 10) -> List[Dict[str, Any]]:
    """Detecta los pools de liquidez más recientes desplegados en DEXes de Base"""
    raw = query_geckoterminal("new_pools")
    if not raw or "data" not in raw:
        return []

    new_pools = []
    for item in raw.get("data", []):
        attrs = item.get("attributes", {})
        reserve = float(attrs.get("reserve_in_usd", 0) or 0)
        if reserve < min_liquidity_usd:
            continue

        vol = attrs.get("volume_usd", {})
        new_pools.append({
            "name": attrs.get("name"),
            "pool_address": attrs.get("address"),
            "pool_created_at": attrs.get("pool_created_at"),
            "base_token_price_usd": float(attrs.get("base_token_price_usd", 0) or 0),
            "reserve_in_usd": round(reserve, 2),
            "volume_24h_usd": round(float(vol.get("h24", 0) or 0), 2),
            "fdv_usd": float(attrs.get("fdv_usd", 0) or 0)
        })

    return new_pools[:limit]

def get_base_token_market_data(token_address: str) -> Optional[Dict[str, Any]]:
    """Consulta métricas de mercado de un token específico en Base"""
    clean_addr = token_address.strip().lower()
    raw = query_geckoterminal(f"tokens/{clean_addr}")
    if not raw or "data" not in raw:
        return None

    attrs = raw.get("data", {}).get("attributes", {})
    return {
        "address": clean_addr,
        "name": attrs.get("name"),
        "symbol": attrs.get("symbol"),
        "decimals": attrs.get("decimals"),
        "price_usd": float(attrs.get("price_usd", 0) or 0),
        "fdv_usd": float(attrs.get("fdv_usd", 0) or 0),
        "total_reserve_in_usd": float(attrs.get("total_reserve_in_usd", 0) or 0),
        "volume_24h_usd": float(attrs.get("volume_usd", {}).get("h24", 0) or 0)
    }

if __name__ == "__main__":
    trending = get_base_trending_pools(min_liquidity_usd=100_000, limit=3)
    print(f"Base DEX Scanner OK. Trending pools (min $100k TVL): {len(trending)}")
    for t in trending:
        print(f" - {t['name']}: Price ${t['base_token_price_usd']:.4f}, 24h Vol: ${t['volume_24h_usd']:,.2f}, TVL: ${t['reserve_in_usd']:,.2f}")
