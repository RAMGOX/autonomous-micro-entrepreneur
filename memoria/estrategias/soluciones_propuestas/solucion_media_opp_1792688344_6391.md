# Solution: [Bounty: $105] Tolerate transient Iris failures in getAttestation and resolveBurn
- **Issue:** [Parabola-org/parabola #3](https://github.com/Parabola-org/parabola/issues/3) / [bounty-plaza #1913](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1913)
- **Bounty:** $105 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Root Cause Analysis
In `src/iris/poll.ts`, `pollForAttestation` allows up to 5 consecutive transient network failures before aborting. In contrast, `getAttestation` called `pollOnce` without retry logic, immediately throwing `IrisRequestError` on the first dropped connection or transient 502/504 gateway error.
Because `resolveBurn` (`src/transfer.ts`) relies on `getAttestation`, this made read-only burn verification fragile and prone to false negatives.

### Implementation Patch

```typescript
// diff --git a/src/iris/retry.ts b/src/iris/retry.ts
export const DEFAULT_MAX_IRIS_CONSECUTIVE_FAILURES = 5;
export const DEFAULT_IRIS_RETRY_DELAY_MS = 1000;

export async function withTransientRetry<T>(
  fn: () => Promise<T>,
  options: {
    maxFailures?: number;
    delayMs?: number;
    signal?: AbortSignal;
  } = {}
): Promise<T> {
  const { maxFailures = DEFAULT_MAX_IRIS_CONSECUTIVE_FAILURES, delayMs = DEFAULT_IRIS_RETRY_DELAY_MS, signal } = options;
  let attempts = 0;

  while (true) {
    signal?.throwIfAborted();
    try {
      return await fn();
    } catch (err) {
      attempts++;
      if (attempts >= maxFailures || signal?.aborted) {
        throw err;
      }
      await new Promise(resolve => setTimeout(resolve, delayMs));
    }
  }
}
```

```typescript
// diff --git a/src/iris/poll.ts b/src/iris/poll.ts
import { withTransientRetry, DEFAULT_MAX_IRIS_CONSECUTIVE_FAILURES } from './retry';

export async function getAttestation(
  messageHash: string,
  options: { maxFailures?: number; signal?: AbortSignal } = {}
): Promise<AttestationResult> {
  // Uses shared retry helper to absorb transient drops
  return await withTransientRetry(
    async () => {
      return await pollOnce(messageHash);
    },
    { maxFailures: options.maxFailures ?? DEFAULT_MAX_IRIS_CONSECUTIVE_FAILURES, signal: options.signal }
  );
}
```

### Unit Verification Tests (`test/iris-transient-retry.test.ts`)

```typescript
import { describe, it, expect, vi } from 'vitest';
import * as irisModule from '../src/iris/poll';

describe('getAttestation transient failure tolerance', () => {
  it('recovers and returns attestation when transient errors occur under threshold', async () => {
    let callCount = 0;
    const pollOnceSpy = vi.spyOn(irisModule, 'pollOnce').mockImplementation(async () => {
      callCount++;
      if (callCount < 3) {
        throw new Error('502 Bad Gateway');
      }
      return { status: 'complete', attestation: '0xabc' } as any;
    });

    const result = await irisModule.getAttestation('0xhash', { maxFailures: 5 });
    expect(result.status).toBe('complete');
    expect(callCount).toBe(3);
  });

  it('fails only when exceeding max consecutive failure limit', async () => {
    vi.spyOn(irisModule, 'pollOnce').mockRejectedValue(new Error('Persistent 500'));

    await expect(irisModule.getAttestation('0xhash', { maxFailures: 3 }))
      .rejects.toThrow('Persistent 500');
  });
});
```
