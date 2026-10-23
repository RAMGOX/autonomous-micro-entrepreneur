---
name: erc8021-attribution
description: >-
  Attach and verify ERC-8021 Schema 0 Builder Code attribution suffixes on Base L2 transactions.
  Use this skill to attribute smart contract calls, bounty claims, and ETH sweeps on Base Mainnet (chainId 8453)
  to ensure on-chain volume tracking on Coinbase CDP SQL, ecosystem rewards, and Base leaderboard indexing.
---

# Base ERC-8021 Attribution Skill

Implements the official **ERC-8021** standard (Schema 0) for transaction attribution via calldata suffixes on Base L2 (`chainId: 8453`).

## 1. Specification & Suffix Byte Layout
ERC-8021 appends trailing bytes directly to the end of transaction calldata. Because the EVM ignores bytes beyond the expected function parameters, transactions execute with 100% safety and zero impact on contract logic.

Layout (read backwards from tail):
$$\text{[TX\_DATA]} + [\text{BUILDER\_CODE}] + [\text{CODE\_LEN (1B)}] + [\text{SCHEMA\_ID (0x00)}] + [\text{ERC\_MARKER (16B)}]$$

- **`ERC_MARKER`**: `0x80218021802180218021802180218021` (16 bytes)
- **`SCHEMA_ID`**: `0x00` (Schema 0: Canonical Registry)
- **`CODE_LEN`**: 1 byte length of ASCII builder code
- **`BUILDER_CODE`**: ASCII string (default: `ame_agent`)

## 2. Python API (`src/erc8021_builder.py`)

```python
from erc8021_builder import (
    encode_erc8021_suffix,
    attach_erc8021_attribution,
    decode_erc8021_attribution
)

# 1. Generate suffix bytes for a builder code
suffix = encode_erc8021_suffix("ame_agent")
# -> bytes with tail 80218021802180218021802180218021

# 2. Attach attribution to any calldata hex
raw_calldata = "0xa9059cbb000000000000000000000000..."
attributed_tx = attach_erc8021_attribution(raw_calldata, "ame_agent")

# 3. Decode attribution from an existing transaction
decoded = decode_erc8021_attribution(attributed_tx)
# -> {'has_attribution': True, 'builder_code': 'ame_agent', 'schema_id': 0}
```

## 3. Local Dashboard REST Endpoints (`http://127.0.0.1:8080`)
- `GET /api/v1/erc8021/info`: Returns configured builder code, hex marker, and standard specs.
- `POST /api/v1/erc8021/attach`: Payload `{"data": "0x...", "builder_code": "ame_agent"}` -> returns attributed calldata.
- `POST /api/v1/erc8021/decode`: Payload `{"data": "0x..."}` -> decodes and returns attribution metadata.
