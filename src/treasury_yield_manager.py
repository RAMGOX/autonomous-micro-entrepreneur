"""
Treasury Yield Manager for Base L2.
Automates yield intelligence, passive cashflow projection, and safe allocation recommendations
for revenue accumulated in the user's Coinbase payout wallet (0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf).
Safety strict: Zero unapproved fund movements. Read-only audits and simulated allocations.
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from defillama_engine import get_base_top_yields, get_base_token_prices
from agentkit_actions import get_agentkit_provider

USER_PAYOUT_WALLET = os.getenv("USER_PAYOUT_WALLET", "0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf")
BOT_WALLET = os.getenv("PUBLIC_ADDRESS_TESTNET", "0x02c1F87F514493F359Afc0B3ff6b587434770361")

def get_treasury_status() -> Dict[str, Any]:
    """Audita balances on-chain en Base L2 para la cartera de cobros y el bot"""
    provider = get_agentkit_provider()
    user_balances = provider.get_balances(USER_PAYOUT_WALLET)
    bot_balances = provider.get_balances(BOT_WALLET)

    prices = get_base_token_prices(["WETH", "USDC", "WDOOM"])
    eth_price = prices.get("WETH", {}).get("price_usd", 2400.0)
    usdc_price = prices.get("USDC", {}).get("price_usd", 1.0)

    user_eth = user_balances.get("ETH", 0.0)
    user_usdc = user_balances.get("tokens", {}).get("USDC", 0.0)
    user_val_usd = (user_eth * eth_price) + (user_usdc * usdc_price)

    bot_eth = bot_balances.get("ETH", 0.0)
    bot_val_usd = bot_eth * eth_price

    return {
        "user_payout_wallet": USER_PAYOUT_WALLET,
        "user_balances": user_balances,
        "user_total_usd_est": round(user_val_usd, 2),
        "bot_wallet": BOT_WALLET,
        "bot_balances": bot_balances,
        "bot_total_usd_est": round(bot_val_usd, 2),
        "eth_price_usd": eth_price,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

def get_recommended_allocations(min_tvl: float = 1_000_000.0) -> List[Dict[str, Any]]:
    """Identifica las mejores oportunidades de staking y yield en Base sin riesgo de impermanent loss"""
    top_stables = get_base_top_yields(min_tvl=min_tvl, stable_only=True, limit=5)
    recommendations = []
    for p in top_stables:
        apy = p.get("apy", 0)
        daily_rate = ((1 + (apy / 100.0)) ** (1 / 365.0) - 1) * 100
        recommendations.append({
            "protocol": p.get("project"),
            "pair": p.get("symbol"),
            "apy": apy,
            "est_daily_yield_pct": round(daily_rate, 4),
            "tvl_usd": p.get("tvl_usd"),
            "risk_profile": "ultra_low" if p.get("il_risk") == "no" else "low",
            "asset_type": "Stablecoin (0 price volatility)",
            "pool_id": p.get("pool_id")
        })
    return recommendations

def simulate_yield_cashflow(amount_usd: float = 100.0) -> Dict[str, Any]:
    """Calcula el flujo de caja pasivo estimado depositando un importe en las mejores bóvedas de Base"""
    recs = get_recommended_allocations()
    if not recs:
        return {"error": "No pools available"}

    best = recs[0]
    apy = best["apy"]
    annual_usd = amount_usd * (apy / 100.0)
    monthly_usd = annual_usd / 12.0
    daily_usd = annual_usd / 365.0

    return {
        "simulated_capital_usd": amount_usd,
        "selected_pool": f"{best['protocol']} ({best['pair']})",
        "apy_pct": apy,
        "projected_daily_earnings_usd": round(daily_usd, 4),
        "projected_monthly_earnings_usd": round(monthly_usd, 2),
        "projected_annual_earnings_usd": round(annual_usd, 2),
        "asset_safety": "USDC/EURC peg backing, no impermanent loss"
    }

if __name__ == "__main__":
    status = get_treasury_status()
    print("Treasury Yield Manager OK.")
    print(f"User Payout Wallet ({USER_PAYOUT_WALLET}): {status['user_balances']}")
    recs = get_recommended_allocations()
    print(f"Top Stable Allocations on Base: {len(recs)} pools found")
    if recs:
        print(f" - Best: {recs[0]['protocol']} {recs[0]['pair']} @ {recs[0]['apy']}% APY")
    sim = simulate_yield_cashflow(100.0)
    print("Simulation for $100:", sim)
