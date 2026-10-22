# Solution: [Bounty: $125] Add structured progress callbacks to transfer()
- **Issue:** [Parabola-org/parabola #6](https://github.com/Parabola-org/parabola/issues/6) / [bounty-plaza #1910](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1910)
- **Bounty:** $125 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Analysis & Problem Statement
Currently, `transfer()` in `src/transfer.ts` executes multiple asynchronous stages sequentially (recipient readiness, allowance check/approval, burn submission, attestation polling, minting). During long transfers (up to 300s timeout), callers have zero stage visibility. This blocks frontend progress bars, webhook notifications, and per-stage latency metrics.

### Implementation Patch

```typescript
// diff --git a/src/types.ts b/src/types.ts
export type TransferProgressEvent =
  | { stage: 'checking_recipient'; recipient: string }
  | { stage: 'approving'; allowanceNeeded: bigint }
  | { stage: 'burning'; sourceChain: string; amount: string }
  | { stage: 'burn_submitted'; burnTxHash: string }
  | { stage: 'polling_attestation'; burnTxHash: string; attempt: number }
  | { stage: 'minting'; destinationChain: string; attestation: string }
  | { stage: 'completed'; burnTxHash: string; mintTxHash: string };

export interface TransferOptionsBase {
  onProgress?: (event: TransferProgressEvent) => void;
  // ... other properties
}
```

```typescript
// diff --git a/src/transfer.ts b/src/transfer.ts
import { TransferProgressEvent } from './types';

export async function transfer(options: TransferOptions): Promise<TransferResult> {
  const { onProgress } = options;

  // 1. Recipient check
  onProgress?.({ stage: 'checking_recipient', recipient: options.recipient });
  await assertStellarRecipientReady(options.recipient);

  // 2. Allowance check/approve
  if (options.sourceChain === 'arc') {
    onProgress?.({ stage: 'approving', allowanceNeeded: options.amountRaw });
    await ensureUsdcAllowance(options.amountRaw);
  }

  // 3. Burn execution
  onProgress?.({ stage: 'burning', sourceChain: options.sourceChain, amount: options.amount });
  const burnTxHash = await executeBurn(options);
  onProgress?.({ stage: 'burn_submitted', burnTxHash });

  // 4. Polling attestation
  let pollAttempt = 0;
  const attestation = await pollForAttestation(burnTxHash, {
    onPoll: () => {
      pollAttempt++;
      onProgress?.({ stage: 'polling_attestation', burnTxHash, attempt: pollAttempt });
    }
  });

  // 5. Mint execution
  onProgress?.({ stage: 'minting', destinationChain: options.destinationChain, attestation: attestation.data });
  const mintTxHash = await executeMint({ ...options, attestation });

  // 6. Complete
  onProgress?.({ stage: 'completed', burnTxHash, mintTxHash });
  return { burnTxHash, mintTxHash, status: 'completed' };
}
```

### Unit Verification Tests (`test/transfer-progress.test.ts`)

```typescript
import { describe, it, expect, vi } from 'vitest';
import { transfer } from '../src/transfer';
import { TransferProgressEvent } from '../src/types';

describe('transfer() onProgress callbacks', () => {
  it('dispatches progress events through full transfer lifecycle', async () => {
    const events: TransferProgressEvent[] = [];
    const onProgress = vi.fn((e: TransferProgressEvent) => events.push(e));

    await transfer({
      sourceChain: 'arc',
      destinationChain: 'stellar',
      amount: '100',
      amountRaw: 100000000n,
      recipient: 'GDESTINATION123',
      onProgress,
      _mockLifecycle: true
    } as any);

    const stages = events.map(e => e.stage);
    expect(stages).toContain('checking_recipient');
    expect(stages).toContain('approving');
    expect(stages).toContain('burning');
    expect(stages).toContain('burn_submitted');
    expect(stages).toContain('polling_attestation');
    expect(stages).toContain('minting');
    expect(stages).toContain('completed');
  });
});
```
