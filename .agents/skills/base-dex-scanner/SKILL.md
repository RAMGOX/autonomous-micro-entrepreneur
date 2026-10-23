---
name: base-dex-scanner
description: >-
  Scan real-time DEX liquidity pools, volume breakouts, and new token deployments on Base L2 using GeckoTerminal API v2.
  Use this skill to identify trending pairs on Base, audit newly launched pools seconds after creation,
  and check on-chain liquidity depth across Aerodrome, Uniswap v3, and SushiSwap without API keys.
---

# Base DEX Scanner Skill

Provides real-time decentralized exchange (DEX) surveillance on Base L2 (`chainId: 8453`) via the GeckoTerminal API v2.

## 1. Core Endpoints
- **Trending Pools:** `https://api.geckoterminal.com/api/v2/networks/base/trending_pools`
- **New Pools:** `https://api.geckoterminal.com/api/v2/networks/base/new_pools`
- **Token Analytics:** `https://api.geckoterminal.com/api/v2/networks/base/tokens/{address}`
- **Zero API Keys Required:** 100% public, free, sub-second responses.

## 2. Python API (`src/dex_scanner.py`)

```python
from dex_scanner import (
    get_base_trending_pools,
    get_base_new_pools,
    get_base_token_market_data
)

# 1. Fetch trending pools on Base with liquidity safety filter (min $50,000)
trending = get_base_trending_pools(min_liquidity_usd=50_000, limit=5)
# Returns name, pool_address, price, volume_24h, reserve_usd, price_change_24h

# 2. Monitor newly created liquidity pools on Base
new_pools = get_base_new_pools(min_liquidity_usd=1_000, limit=5)
# Returns pool_created_at, reserve_usd, price, fdv

# 3. Query market metrics for any token on Base
token_data = get_base_token_market_data("0x940181a94A35A4569E4529A3CDfB74e48FD98AE3") # AERO
```

## 3. Local Dashboard REST Endpoints (`http://127.0.0.1:8080`)
- `GET /api/v1/dex/trending?min_liquidity=50000&limit=10`: Top trending liquidity pools.
- `GET /api/v1/dex/new_pools?min_liquidity=1000&limit=10`: Newly deployed DEX pools.
- `GET /api/v1/dex/token?address=<0x...>`: Token analytics, market cap, and volume.
