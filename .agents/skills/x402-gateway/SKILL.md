---
name: x402-gateway
description: >-
  Monetize AI agent services and on-chain intelligence on Base L2 using the HTTP 402 Payment Required standard (x402.org).
  Use this skill when exposing, configuring, or interacting with pay-per-request endpoints that require micro-payments
  in ETH or USDC on Base Mainnet directly to the user's payout wallet.
---

# x402 HTTP Micropayment Gateway Skill (Base L2)

This skill describes the x402 protocol integration enabling inbound revenue generation for the Autonomous Micro-Entrepreneur.

## 1. Overview & Standard Architecture

The **x402 protocol** (inspired by RFC 9110 HTTP 402) allows internet-native, programmatic micropayments for AI services without credit cards, API keys, or subscriptions.

- **Network:** Base Mainnet (`chainId: 8453`)
- **Recipient Address (Payee):** `0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf` (User Coinbase Wallet)
- **Base RPC:** `https://mainnet.base.org`
- **Specification:** `https://x402.org`

## 2. Gateway Endpoints (`http://127.0.0.1:8080`)

### `GET /api/v1/x402/pricing`
Returns live pricing and service specifications.
- Response: `200 OK` with JSON specifying required fees per service.

### `POST /api/v1/x402/solve`
Solves complex coding, auditing, or technical queries using the multi-brain architecture (Cerebro 1/3).
- Unpaid Request: Returns `402 Payment Required` with `WWW-Authenticate: x402-v1` and fee details (0.0001 ETH).
- Paid Request: Include header `X-Payment-Tx: <0x_tx_hash>`. Verifies on-chain payment on Base, prevents replays, executes prompt, and returns solution.

### `GET /api/v1/x402/intel`
Provides live curated bounty data and market intelligence on Base.
- Fee: `0.00005 ETH` (~$0.13 USD).
- Unpaid Request: Returns `402 Payment Required`.
- Paid Request: Returns top verified bounty opportunities.

## 3. Anti-Replay & Security Flow

1. Every incoming transaction hash is verified against Base Mainnet RPC (`w3.eth.get_transaction_receipt` and `w3.eth.get_transaction`).
2. Checks:
   - `receipt.status == 1`
   - `tx.to == USER_PAYOUT_WALLET`
   - `tx.value >= required_wei`
3. Consumed transaction hashes are persisted to `memoria/estado/x402_processed_txs.json`. Reusing the same hash returns `400 Bad Request`.
4. Verified payments immediately trigger Discord notifications to `#general` and `#dashboard-24-7`.
