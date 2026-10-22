# Solution: Skip the Arc approve transaction when existing allowance covers the burn
- **Issue:** [Parabola-org/parabola #8](https://github.com/Parabola-org/parabola/issues/8) / [bounty-plaza #1908](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1908)
- **Bounty:** $90 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Analysis & Problem Statement
Currently, `burn()` in `src/transfer.ts` unconditionally calls `approveUsdcOnArc` before executing an Arc-sourced burn. This causes an unnecessary ERC-20 `approve` transaction even when `TokenMessengerV2` already holds an allowance greater than or equal to `amountRaw` (e.g. from previous transfers or pre-approvals). This incurs extra gas fees, increases nonce contention on high-frequency hot wallets, and adds confirmation latency.

### Implementation Patch

```typescript
// diff --git a/src/chains/arc.ts b/src/chains/arc.ts
// Add helper to read existing USDC allowance
import { erc20Abi } from 'viem';
import { publicClient } from './client';
import { ARC_USDC_ADDRESS, TOKEN_MESSENGER_V2_ADDRESS } from '../constants';

export async function getUsdcAllowanceOnArc(owner: `0x${string}`, spender: `0x${string}` = TOKEN_MESSENGER_V2_ADDRESS): Promise<bigint> {
  return await publicClient.readContract({
    address: ARC_USDC_ADDRESS,
    abi: erc20Abi,
    functionName: 'allowance',
    args: [owner, spender],
  });
}
```

```typescript
// diff --git a/src/transfer.ts b/src/transfer.ts
// In burn(): query current allowance before dispatching approve transaction
import { getUsdcAllowanceOnArc, approveUsdcOnArc } from './chains/arc';
import { TOKEN_MESSENGER_V2_ADDRESS } from './constants';

export async function burn(
  sourceChain: string,
  owner: `0x${string}`,
  amountRaw: bigint,
  destinationDomain: number,
  mintRecipient: `0x${string}`
) {
  if (sourceChain === 'arc') {
    // Check existing allowance first (read call is free/fast)
    const currentAllowance = await getUsdcAllowanceOnArc(owner, TOKEN_MESSENGER_V2_ADDRESS);
    if (currentAllowance < amountRaw) {
      console.log(`[transfer] Allowance (${currentAllowance}) < amountRaw (${amountRaw}). Approving...`);
      await approveUsdcOnArc(amountRaw);
    } else {
      console.log(`[transfer] Existing allowance (${currentAllowance}) covers amountRaw (${amountRaw}). Skipping approve.`);
    }
  }

  // Proceed with depositForBurn call
  return await executeBurn(sourceChain, amountRaw, destinationDomain, mintRecipient);
}
```

### Unit Verification Tests (`test/transfer-approval.test.ts`)

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as arcModule from '../src/chains/arc';
import { burn } from '../src/transfer';

describe('Arc burn allowance skip check', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('skips approve when existing allowance >= amountRaw', async () => {
    const allowanceSpy = vi.spyOn(arcModule, 'getUsdcAllowanceOnArc').mockResolvedValue(2000000n);
    const approveSpy = vi.spyOn(arcModule, 'approveUsdcOnArc').mockResolvedValue('0xhash' as any);

    await burn('arc', '0x1111111111111111111111111111111111111111', 1000000n, 0, '0x2222222222222222222222222222222222222222');

    expect(allowanceSpy).toHaveBeenCalledTimes(1);
    expect(approveSpy).not.toHaveBeenCalled();
  });

  it('triggers approve when existing allowance < amountRaw', async () => {
    const allowanceSpy = vi.spyOn(arcModule, 'getUsdcAllowanceOnArc').mockResolvedValue(500000n);
    const approveSpy = vi.spyOn(arcModule, 'approveUsdcOnArc').mockResolvedValue('0xhash' as any);

    await burn('arc', '0x1111111111111111111111111111111111111111', 1000000n, 0, '0x2222222222222222222222222222222222222222');

    expect(allowanceSpy).toHaveBeenCalledTimes(1);
    expect(approveSpy).toHaveBeenCalledWith(1000000n);
  });
});
```
