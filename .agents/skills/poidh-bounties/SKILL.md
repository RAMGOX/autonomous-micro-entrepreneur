---
name: poidh-bounties
description: >-
  Interact with the POIDH (Pics Or It Didn't Happen) on-chain bounty protocol on Base L2 (chainId 8453) and Arbitrum (chainId 42161).
  Use this skill when scanning open bounties, inspecting claims, checking on-chain claim acceptance,
  broadcasting automated claim transactions, and sweeping ETH payouts to the user's wallet.
---

# POIDH Bounty Hunter & Automated Settlement Skill

This skill provides direct runbooks and API integrations for the POIDH protocol on Base L2.

## 1. Network & Protocol Endpoints

- **Chain:** Base Mainnet (`chainId: 8453`)
- **Base RPC:** `https://mainnet.base.org`
- **POIDH v3 Contract (Base):** `0x5555fa783936c260f77385b4e153b9725fef1719`
- **Official REST Indexer:** `https://indexer.poidh.xyz/api/v1`
  - Swagger UI: `https://indexer.poidh.xyz/swagger`
  - OpenAPI Spec: `https://indexer.poidh.xyz/openapi/doc`
- **Fallback MCP Endpoint:** `https://poidh.xyz/api/mcp`
- **Official Skill Spec:** `https://poidh.xyz/skill.md`

## 2. Core Operational Procedures

### A. Scanning Active Bounties (High-Speed Indexer)
To retrieve active open bounties on Base without JSON-RPC streaming delays:
```http
GET https://indexer.poidh.xyz/api/v1/bounties?chainId=8453&inProgress=true&limit=100
```
Filter criteria:
1. `inProgress == true`
2. `isCanceled == false`
3. Digital / Software solvable tasks (exclude physical, location-specific, or video tasks).

### B. Inspecting Wallet Claims & Acceptance Status
Query all claims belonging to an automated wallet in a single call:
```http
GET https://indexer.poidh.xyz/api/v1/claims?chainId=8453&issuer={WALLET_ADDRESS}
```
Check:
- `isAccepted`: If `true`, the bounty issuer has released funds on-chain.
- `bountyId`: The on-chain bounty ID.
- `onChainId`: The claim ID.

### C. Direct On-Chain Claim Submission
1. Call `prepare_submit_claim` against `https://poidh.xyz/api/mcp` to retrieve calldata and destination contract address.
2. Sign raw transaction with bot's local private key (`PRIVATE_KEY_TESTNET`).
3. Broadcast via `w3.eth.send_raw_transaction` to Base Mainnet RPC (`https://mainnet.base.org`).
4. Gas cost: ~0.000003 ETH per claim.

### D. Automated Sweep of Rewards
When a claim is marked `isAccepted == true` or bot wallet balance exceeds `0.0008 ETH`:
1. Calculate reserve (0.0001 ETH preserved for future submission gas).
2. Transfer remaining balance directly to user's Coinbase Wallet: `USER_PAYOUT_WALLET` (`0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf`).
3. Notify Discord `#general` and `#dashboard-24-7`.
