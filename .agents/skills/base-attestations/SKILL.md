---
name: base-attestations
description: >-
  Query and verify Ethereum Attestation Service (EAS) proofs, on-chain reputations, and Coinbase verifications on Base L2.
  Use this skill when auditing counterparty credibility, verifying EAS bounty completion attestations (Bountycaster / Gitcoin),
  or analyzing on-chain trust scores for wallets on Base Mainnet.
---

# Base EAS Attestations Skill

Provides native, zero-gas on-chain attestation queries for Base L2 (`chainId: 8453`) using the Ethereum Attestation Service (EAS) decentralized indexer.

## 1. Verified Protocol Contracts & Endpoints on Base
- **Network:** Base Mainnet (`chainId: 8453`)
- **EAS Contract:** `0x4200000000000000000000000000000000000021`
- **EAS GraphQL Indexer:** `https://base.easscan.org/graphql`
- **EAS Explorer:** `https://base.easscan.org`

## 2. Python API (`src/eas_indexer.py`)

```python
from eas_indexer import (
    get_address_attestations,
    get_address_reputation,
    get_recent_attestations
)

# 1. Check wallet reputation & Coinbase verification
rep = get_address_reputation("0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf")
# Returns: {
#   "trust_score": 40,
#   "coinbase_verified": True,
#   "total_attestations_received": 1,
#   "unique_attesters_count": 1
# }

# 2. Get full attestation history for any address
history = get_address_attestations("0x...", limit=10)

# 3. Stream recent attestations on Base
latest = get_recent_attestations(limit=5)
```

## 3. Local Dashboard REST Endpoints (`http://127.0.0.1:8080`)
- `GET /api/v1/eas/reputation?address=<0x...>`: Calculates synthetic trust score, Coinbase verification badge, and attester summary.
- `GET /api/v1/eas/attestations?address=<0x...>&limit=10`: Returns raw on-chain attestations (sent & received).
- `GET /api/v1/eas/latest?limit=10`: Streams most recent attestations broadcast to Base Mainnet.
