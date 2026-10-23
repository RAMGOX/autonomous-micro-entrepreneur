"""
DefiLlama Base Engine: Motor de Inteligencia Financiera Descentralizada para Base L2.
Consulta en tiempo real rendimientos (APY/APR), TVL, liquidez de protocolos (Aerodrome, Uniswap, Aave, Moonwell)
y cotizaciones multi-token en Base L2 sin requerir claves API ni incurrir en costes.
APIs públicas oficiales: https://yields.llama.fi y https://coins.llama.fi.
"""
import json
import time
import urllib.request
from typing import Dict, Any, List, Optional

YIELDS_API_URL = "https://yields.llama.fi/pools"
COINS_API_URL = "https://coins.llama.fi/prices/current"

# Direcciones oficiales de tokens en Base Mainnet (8453)
KNOWN_BASE_TOKENS = {
    "ETH": "base:0x0000000000000000000000000000000000000000",
    "WETH": "base:0x4200000000000000000000000000000000000006",
    "USDC": "base:0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "CBBTC": "base:0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
    "AERO": "base:0x940181a94A35A4569E4529A3CDfB74e48FD98AE3",
    "WDOOM": "base:0x623c84A5E04bF715018203334b0eFE41696eBC3E"
}

_cache = {
    "yields_data": None,
    "yields_time": 0
}

def fetch_base_pools(cache_ttl: int = 300) -> List[Dict[str, Any]]:
    """Obtiene y cachea todos los pools de liquidez y préstamo activos en Base L2"""
    now = time.time()
    if _cache["yields_data"] and (now - _cache["yields_time"]) < cache_ttl:
        return _cache["yields_data"]

    req = urllib.request.Request(
        YIELDS_API_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutonomousMicroEntrepreneur/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as res:
            raw = json.loads(res.read().decode("utf-8"))
            all_pools = raw.get("data", [])
            base_pools = [p for p in all_pools if p.get("chain") == "Base"]
            _cache["yields_data"] = base_pools
            _cache["yields_time"] = now
            return base_pools
    except Exception as e:
        if _cache["yields_data"]:
            return _cache["yields_data"]
        return []

def get_base_top_yields(
    min_tvl: float = 500_000.0,
    symbol_filter: Optional[str] = None,
    stable_only: bool = False,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Filtra los pools con mayor APY en Base cumpliendo criterios de seguridad de liquidez.
    """
    pools = fetch_base_pools()
    filtered = []
    sym = symbol_filter.upper() if symbol_filter else None

    for p in pools:
        tvl = p.get("tvlUsd", 0) or 0
        if tvl < min_tvl:
            continue
        if stable_only and not p.get("stablecoin", False):
            continue
        pool_symbol = p.get("symbol", "").upper()
        if sym and sym not in pool_symbol:
            continue

        apy = p.get("apy", 0) or 0
        filtered.append({
            "project": p.get("project"),
            "symbol": p.get("symbol"),
            "tvl_usd": round(tvl, 2),
            "apy": round(apy, 2),
            "apy_base": round(p.get("apyBase") or 0, 2),
            "apy_reward": round(p.get("apyReward") or 0, 2),
            "pool_id": p.get("pool"),
            "stablecoin": p.get("stablecoin", False),
            "il_risk": p.get("ilRisk", "no")
        })

    filtered.sort(key=lambda x: x["apy"], reverse=True)
    return filtered[:limit]

def get_base_token_prices(tokens: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Consulta cotizaciones en tiempo real en Base L2 vía DefiLlama Coins API.
    Acepta símbolos conocidos ('WETH', 'USDC', 'AERO') o direcciones completas ('base:0x...').
    """
    targets = []
    symbol_map = {}
    tokens = tokens or ["WETH", "USDC", "AERO", "CBBTC"]

    for t in tokens:
        clean = t.strip()
        upper = clean.upper()
        if upper in KNOWN_BASE_TOKENS:
            addr = KNOWN_BASE_TOKENS[upper]
            targets.append(addr)
            symbol_map[addr.lower()] = upper
        elif clean.startswith("0x"):
            addr = f"base:{clean}"
            targets.append(addr)
            symbol_map[addr.lower()] = clean
        elif clean.startswith("base:"):
            targets.append(clean)
            symbol_map[clean.lower()] = clean

    if not targets:
        return {}

    url = f"{COINS_API_URL}/{','.join(targets)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutonomousMicroEntrepreneur/1.0"}
    )
    results = {}
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode("utf-8")).get("coins", {})
            for coin_key, info in data.items():
                sym = symbol_map.get(coin_key.lower(), info.get("symbol"))
                results[sym] = {
                    "price_usd": info.get("price"),
                    "decimals": info.get("decimals"),
                    "confidence": info.get("confidence"),
                    "timestamp": info.get("timestamp")
                }
    except Exception as e:
        pass
    return results

def get_base_defi_overview() -> Dict[str, Any]:
    """Genera un resumen ejecutivo de salud y oportunidades de rendimiento en Base L2"""
    pools = fetch_base_pools()
    total_tvl = sum(p.get("tvlUsd", 0) or 0 for p in pools)
    top_yields = get_base_top_yields(min_tvl=1_000_000, limit=5)
    stable_yields = get_base_top_yields(min_tvl=1_000_000, stable_only=True, limit=3)
    prices = get_base_token_prices(["WETH", "USDC", "AERO"])

    return {
        "network": "base",
        "tracked_pools_count": len(pools),
        "total_tvl_tracked_usd": round(total_tvl, 2),
        "market_prices": prices,
        "top_liquid_yields": top_yields,
        "top_stable_yields": stable_yields,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

if __name__ == "__main__":
    overview = get_base_defi_overview()
    print("DefiLlama Base Engine OK.")
    print(f"Tracked pools on Base: {overview['tracked_pools_count']}, Total TVL: ${overview['total_tvl_tracked_usd']:,.2f}")
    print(f"Sample prices: {overview['market_prices']}")
