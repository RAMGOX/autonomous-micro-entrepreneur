---
name: defillama-base
description: >-
  Query real-time DeFi yields, liquidity pools (Aerodrome, Uniswap v3, Aave, Moonwell), TVL, and token spot prices on Base L2.
  Use this skill to identify high-yield staking or LP opportunities on Base, monitor token market conditions,
  or evaluate DeFi protocol stability without requiring API keys or incurring gas costs.
---

# Base DefiLlama Intelligence Skill

Provides decentralized financial telemetry for the Base L2 (`chainId: 8453`) ecosystem via the official DefiLlama REST APIs.

## 1. Core Endpoints & Capabilities
- **Yields API:** `https://yields.llama.fi/pools` (monitors >2,200 active pools on Base)
- **Coins API:** `https://coins.llama.fi/prices/current` (multi-token pricing with confidence scores)
- **Zero API Keys Required:** 100% public, free, sub-second responses.

## 2. Python API (`src/defillama_engine.py`)

```python
from defillama_engine import (
    get_base_top_yields,
    get_base_token_prices,
    get_base_defi_overview
)

# 1. Macro overview of Base DeFi ecosystem
overview = get_base_defi_overview()
# -> {'tracked_pools_count': 2252, 'total_tvl_tracked_usd': 8116915220, ...}

# 2. Top yield opportunities for USDC on Base
usdc_yields = get_base_top_yields(min_tvl=1_000_000, symbol_filter="USDC", limit=5)
# Returns pools with APY, base APY, reward APY, and protocol ID

# 3. Real-time token market prices on Base
prices = get_base_token_prices(["WETH", "USDC", "AERO", "CBBTC"])
# -> {'WETH': {'price_usd': 2406.6, ...}, 'USDC': {'price_usd': 0.999, ...}}
```

## 3. Local Dashboard REST Endpoints (`http://127.0.0.1:8080`)
- `GET /api/v1/defi/overview`: Macro stats of Base network TVL, pool count, and prices.
- `GET /api/v1/defi/yields?limit=10&min_tvl=500000&symbol=USDC&stable=true`: Filtered yield rankings.
- `GET /api/v1/defi/prices?tokens=WETH,USDC,AERO`: Multi-token spot pricing on Base.
