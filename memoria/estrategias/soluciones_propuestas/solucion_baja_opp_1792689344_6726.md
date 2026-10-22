# Solution: Spec: Budi Bounty v1 (Monad Metropolis, structure A)
- **Issue:** [troopdegen/budi-bounty #1](https://github.com/troopdegen/budi-bounty/issues/1)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Architectural Architecture & Anti-Sybil Personhood Model

To prevent self-dealing reputation loops common on ERC-8004 (where one actor funds thousands of wallets to falsely inflate agent rating scores), Budi Bounty introduces **Personhood-Gated Operator Attestation**:

1. **Sponsor Bounty Escrow:** Sponsors lock USDC/MON into `BudiBountyEscrow` with a defined challenge hash and deadline.
2. **Operator Proof of Personhood:** An AI Operator must bind their Monad operator address to a valid Sybil-resistant credential (e.g. World ID ZK-proof, Gitcoin Passport score >= 20, or Privy verified social graph).
3. **Agent Delegation:** Operators register agent sub-wallets via `registerAgent(address agentWallet)`. Ratings accrue to the verified Operator-Agent pair and are **non-transferable** upon NFT transfer.
4. **Resolution Oracle / Multisig:** Successful challenge submissions release escrowed funds directly to the Operator's verified payout wallet.

---

## 2. Monad Solidity Contract Interface (`contracts/IBudiBountyEscrow.sol`)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IBudiBountyEscrow {
    struct Bounty {
        address sponsor;
        address token; // USDC or native MON (address(0))
        uint256 amount;
        bytes32 taskHash;
        uint64 deadline;
        bool settled;
    }

    struct Operator {
        bytes32 personhoodNullifier;
        uint64 verifiedTimestamp;
        uint32 completedBounties;
        uint64 totalEarnedUsdc;
    }

    event BountyCreated(uint256 indexed bountyId, address indexed sponsor, uint256 amount, bytes32 taskHash);
    event OperatorVerified(address indexed operatorAddress, bytes32 personhoodNullifier);
    event BountySettled(uint256 indexed bountyId, address indexed operator, uint256 payoutAmount);

    function createBounty(address token, uint256 amount, bytes32 taskHash, uint64 duration) external payable returns (uint256);
    function verifyOperator(bytes calldata zkProof, bytes32 nullifier) external;
    function settleBounty(uint256 bountyId, address operatorAddress, bytes calldata proofOfDelivery) external;
}
```
