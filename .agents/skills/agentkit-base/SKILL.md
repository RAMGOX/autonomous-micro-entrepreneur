---
name: agentkit-base
description: >-
  Execute on-chain Web3 actions on Base L2 (chainId 8453) using the Coinbase AgentKit Action Provider pattern.
  Use this skill when resolving Basenames (.base.eth) via L2Resolver, querying decentralized spot prices from Uniswap v3,
  checking multi-token balances (ETH, USDC, WDOOM), or estimating on-chain token swaps.
---

# Base AgentKit Action Provider Skill

This skill provides native, zero-dependency Web3 actions for AI agents interacting with the Base L2 ecosystem.

## 1. Verified Protocol Contracts on Base Mainnet

- **Network:** Base Mainnet (`chainId: 8453`)
- **Base RPC:** `https://mainnet.base.org`
- **Basename L2Resolver:** `0xC6d566A56A1aFf6508b41f6c90ff131615583BCD`
- **Uniswap v3 QuoterV2:** `0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a`
- **Native USDC on Base:** `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- **WETH on Base:** `0x4200000000000000000000000000000000000006`
- **wDOOM on Base:** `0x623c84A5E04bF715018203334b0eFE41696eBC3E`

## 2. Core Capabilities & Python API

Available via `src/agentkit_actions.py`:

```python
from agentkit_actions import get_agentkit_provider

provider = get_agentkit_provider()

# 1. Resolve Basenames (.base.eth)
res = provider.resolve_basename("jesse.base.eth")
# -> {'status': 'success', 'name': 'jesse.base.eth', 'address': '0x2211d1D0020DAEA8039E46Cf1367962070d77DA9'}

# 2. Get Decentralized Spot Price (Uniswap v3 Quoter on Base)
price = provider.get_eth_spot_price_usdc()
# -> 2405.04 USD (Zero API keys, 100% on-chain)

# 3. Multi-Token Balance Query
bal = provider.get_balances("0x02c1F87F514493F359Afc0B3ff6b587434770361")
# -> {'ETH': 0.000452, 'tokens': {'USDC': 0.0, 'WDOOM': 3000}}

# 4. Swap Estimation
swap = provider.estimate_swap(0.05)
# -> {'expected_output_usdc': 120.25, 'effective_rate': 2405.14}
```

## 3. HTTP Endpoints on Local Dashboard (`http://127.0.0.1:8080`)

### `GET /api/v1/agentkit/action?action=resolve_basename&name=jesse.base.eth`
Resolves `.base.eth` human-readable names to checksummed addresses.

### `GET /api/v1/agentkit/action?action=get_spot_price`
Returns real-time on-chain Uniswap v3 spot price of ETH in USDC.

### `GET /api/v1/agentkit/action?action=get_balances&wallet=0x...`
Returns ETH and token holdings on Base.

### `POST /api/v1/agentkit/action`
Accepts JSON payload `{"action": "estimate_swap", "params": {"amount_eth": 0.05}}`.
