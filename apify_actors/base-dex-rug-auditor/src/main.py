"""
Apify Actor: Base L2 Token Liquidity & Rug Risk Auditor (MCP Ready).
"""
import asyncio
import requests


def audit_base_token(address: str) -> dict:
    addr = address.strip().lower()
    gt_url = f"https://api.geckoterminal.com/api/v2/networks/base/tokens/{addr}"
    r = requests.get(gt_url, headers={"Accept": "application/json"}, timeout=12)
    if r.status_code != 200:
        return {"address": addr, "found": False, "risk_level": "CRITICAL_UNINDEXED", "safety_score": 0}

    attrs = r.json().get("data", {}).get("attributes", {})
    reserve_usd = float(attrs.get("total_reserve_in_usd") or 0.0)
    vol_24h = float((attrs.get("volume_usd") or {}).get("h24") or 0.0)
    fdv_usd = float(attrs.get("fdv_usd") or 0.0)

    score = 100
    warnings = []
    if reserve_usd < 10000:
        score -= 55
        warnings.append("Low liquidity (<$10k USD)")
    elif reserve_usd < 50000:
        score -= 25
        warnings.append("Moderate liquidity (<$50k USD)")
    if vol_24h < 1000:
        score -= 20
        warnings.append("Low 24h trading volume")
    if fdv_usd > 0 and reserve_usd > 0 and (fdv_usd / reserve_usd) > 100:
        score -= 20
        warnings.append("High FDV-to-Liquidity ratio (>100x)")

    score = max(0, score)
    risk = "LOW" if score >= 75 else ("MEDIUM" if score >= 45 else "HIGH")
    return {
        "address": addr,
        "found": True,
        "name": attrs.get("name"),
        "symbol": attrs.get("symbol"),
        "price_usd": attrs.get("price_usd"),
        "liquidity_reserve_usd": round(reserve_usd, 2),
        "volume_24h_usd": round(vol_24h, 2),
        "fdv_usd": round(fdv_usd, 2),
        "safety_score": score,
        "risk_level": risk,
        "warnings": warnings
    }


async def main():
    from apify import Actor
    async with Actor:
        inp = await Actor.get_input() or {}
        addrs = inp.get("tokenAddresses") or ["0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"]
        for a in addrs[:50]:
            await Actor.push_data(audit_base_token(a))


if __name__ == "__main__":
    asyncio.run(main())
