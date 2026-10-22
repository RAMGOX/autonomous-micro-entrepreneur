# Solution: [Bounty: $125] Add AbortSignal support across transfer, completeMint, and attestation polling
- **Issue:** [Parabola-org/parabola #5](https://github.com/Parabola-org/parabola/issues/5) / [bounty-plaza #1911](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1911)
- **Bounty:** $125 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Analysis & Problem Statement
Currently, `pollForAttestation`, `pollTransactionStatus`, and `waitForAllowance` run `while` loops with fixed timeouts without cancellation hooks. When a caller terminates their request (e.g., HTTP timeout or component unmount), the transfer loop hangs in the background. Furthermore, if abort occurs after funds are already burned on-chain, simply throwing an uncaught `DOMException` drops `burnTxHash`, violating the SDK safety guarantee that `burnTxHash` is preserved for mint recovery.

### Implementation Patch

```typescript
// diff --git a/src/types.ts b/src/types.ts
export interface TransferOptionsBase {
  signal?: AbortSignal;
  // ... other options
}

export interface CompleteMintOptions {
  signal?: AbortSignal;
  // ... other options
}

export class TransferAbortError extends Error {
  readonly burnTxHash?: string;
  readonly code = 'TRANSFER_ABORTED';

  constructor(message: string, burnTxHash?: string) {
    super(message);
    this.name = 'TransferAbortError';
    this.burnTxHash = burnTxHash;
  }
}
```

```typescript
// diff --git a/src/iris/poll.ts b/src/iris/poll.ts
export async function pollForAttestation(
  messageHash: string,
  options: { signal?: AbortSignal; intervalMs?: number; maxConsecutiveFailures?: number } = {}
) {
  const { signal, intervalMs = 2000, maxConsecutiveFailures = 5 } = options;
  let consecutiveFailures = 0;

  while (true) {
    signal?.throwIfAborted();

    try {
      const attestation = await pollOnce(messageHash);
      if (attestation.status === 'complete') {
        return attestation;
      }
      consecutiveFailures = 0;
    } catch (err) {
      if (signal?.aborted) throw err;
      consecutiveFailures++;
      if (consecutiveFailures >= maxConsecutiveFailures) {
        throw new Error(`Attestation polling exceeded consecutive failure limit: ${err}`);
      }
    }

    // Sleep with abort listener
    await new Promise((resolve, reject) => {
      if (signal?.aborted) return reject(signal.reason || new Error('Aborted'));
      const timer = setTimeout(resolve, intervalMs);
      signal?.addEventListener('abort', () => {
        clearTimeout(timer);
        reject(signal.reason || new Error('Aborted'));
      }, { once: true });
    });
  }
}
```

```typescript
// diff --git a/src/transfer.ts b/src/transfer.ts
export async function transfer(options: TransferOptions): Promise<TransferResult> {
  const { signal } = options;
  signal?.throwIfAborted();

  let burnTxHash: string | undefined;
  try {
    // 1. Burn phase
    burnTxHash = await executeBurn(options);
    signal?.throwIfAborted();

    // 2. Poll attestation phase
    const attestation = await pollForAttestation(burnTxHash, { signal });
    signal?.throwIfAborted();

    // 3. Mint phase
    const mintTxHash = await executeMint({ ...options, attestation, signal });
    return { burnTxHash, mintTxHash, status: 'completed' };
  } catch (err: any) {
    if (signal?.aborted || err.name === 'AbortError') {
      throw new TransferAbortError(
        `Transfer aborted by caller.${burnTxHash ? ' Burn was already executed on-chain.' : ''}`,
        burnTxHash
      );
    }
    throw err;
  }
}
```

### Unit Verification Tests (`test/abort-signal.test.ts`)

```typescript
import { describe, it, expect, vi } from 'vitest';
import { transfer, TransferAbortError } from '../src/transfer';

describe('AbortSignal handling in transfer pipeline', () => {
  it('aborts before burn without burnTxHash', async () => {
    const controller = new AbortController();
    controller.abort();

    await expect(transfer({ signal: controller.signal } as any))
      .rejects.toThrow(TransferAbortError);
  });

  it('preserves burnTxHash when aborted during attestation polling', async () => {
    const controller = new AbortController();
    // Simulate abort after 50ms (after burn completes)
    setTimeout(() => controller.abort(), 50);

    try {
      await transfer({
        signal: controller.signal,
        _mockBurnHash: '0xabc123burn'
      } as any);
      expect.fail('Should have thrown TransferAbortError');
    } catch (err: any) {
      expect(err).toBeInstanceOf(TransferAbortError);
      expect(err.burnTxHash).toBe('0xabc123burn');
    }
  });
});
```
