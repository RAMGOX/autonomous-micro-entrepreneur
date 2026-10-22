# Solution: [Bounty: $75] Expose retry/backoff knobs for Stellar allowance wait and RPC-lag retry
- **Issue:** [Parabola-org/parabola #12](https://github.com/Parabola-org/parabola/issues/12) / [bounty-plaza #1904](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1904)
- **Bounty:** $75 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Root Cause Analysis
In `src/chains/stellar.ts`, `waitForAllowance` hard-codes 6 attempts with 1500ms delay, and `retryOnTransientRpcLag` hard-codes 3 attempts with 2000ms delay. Callers on public or rate-limited Stellar Horizon nodes cannot increase retry attempts to absorb RPC congestion, nor can latency-sensitive environments configure shorter timeouts to fail fast.

### Implementation Patch

```typescript
// diff --git a/src/types.ts b/src/types.ts
export interface StellarRetryOptions {
  allowanceMaxAttempts?: number;
  allowanceIntervalMs?: number;
  rpcLagMaxAttempts?: number;
  rpcLagIntervalMs?: number;
}

export interface TransferOptionsBase {
  stellarRetry?: StellarRetryOptions;
  // ... other properties
}
```

```typescript
// diff --git a/src/chains/stellar.ts b/src/chains/stellar.ts
import { StellarRetryOptions } from '../types';

export const DEFAULT_STELLAR_RETRY_CONFIG: Required<StellarRetryOptions> = {
  allowanceMaxAttempts: 6,
  allowanceIntervalMs: 1500,
  rpcLagMaxAttempts: 3,
  rpcLagIntervalMs: 2000,
};

export async function waitForAllowance(
  server: any,
  owner: string,
  spender: string,
  minAllowance: bigint,
  options?: StellarRetryOptions
): Promise<bigint> {
  const maxAttempts = options?.allowanceMaxAttempts ?? DEFAULT_STELLAR_RETRY_CONFIG.allowanceMaxAttempts;
  const intervalMs = options?.allowanceIntervalMs ?? DEFAULT_STELLAR_RETRY_CONFIG.allowanceIntervalMs;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const allowance = await getAllowance(server, owner, spender);
    if (allowance >= minAllowance) {
      return allowance;
    }
    if (attempt < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, intervalMs));
    }
  }

  throw new Error(`Timed out waiting for Stellar allowance after ${maxAttempts} attempts.`);
}

export async function retryOnTransientRpcLag<T>(
  action: () => Promise<T>,
  options?: StellarRetryOptions
): Promise<T> {
  const maxAttempts = options?.rpcLagMaxAttempts ?? DEFAULT_STELLAR_RETRY_CONFIG.rpcLagMaxAttempts;
  const intervalMs = options?.rpcLagIntervalMs ?? DEFAULT_STELLAR_RETRY_CONFIG.rpcLagIntervalMs;

  let lastError: unknown;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await action();
    } catch (err) {
      lastError = err;
      if (attempt < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, intervalMs));
      }
    }
  }
  throw lastError;
}
```

### Unit Verification Tests (`test/stellar-retry-knobs.test.ts`)

```typescript
import { describe, it, expect, vi } from 'vitest';
import { waitForAllowance, retryOnTransientRpcLag } from '../src/chains/stellar';

describe('Stellar retry knobs configuration', () => {
  it('respects caller configured allowanceMaxAttempts and intervalMs', async () => {
    let calls = 0;
    const serverMock = {};
    vi.stubGlobal('getAllowance', vi.fn().mockImplementation(async () => {
      calls++;
      return 0n; // Never reaches min
    }));

    await expect(waitForAllowance(serverMock, 'G1', 'G2', 100n, {
      allowanceMaxAttempts: 2,
      allowanceIntervalMs: 10
    })).rejects.toThrow('Timed out waiting for Stellar allowance after 2 attempts.');

    expect(calls).toBe(2);
  });

  it('respects caller configured rpcLagMaxAttempts', async () => {
    let attempts = 0;
    const action = vi.fn().mockImplementation(async () => {
      attempts++;
      throw new Error('RPC glitch');
    });

    await expect(retryOnTransientRpcLag(action, {
      rpcLagMaxAttempts: 4,
      rpcLagIntervalMs: 5
    })).rejects.toThrow('RPC glitch');

    expect(attempts).toBe(4);
  });
});
```
