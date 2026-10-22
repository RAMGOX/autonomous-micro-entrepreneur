# Solution: [Bounty: $105] Stop silently pricing Fast Transfers at zero when Iris returns no fast tier
- **Issue:** [Parabola-org/parabola #2](https://github.com/Parabola-org/parabola/issues/2) / [bounty-plaza #1914](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1914)
- **Bounty:** $105 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Root Cause Analysis
In `src/iris/poll.ts`, `fetchFastTransferFeeBps` executes:
```typescript
const fastEntry = body.find((entry) => entry.finalityThreshold <= 1000);
return fastEntry?.minimumFee ?? 0;
```
If the Iris API returns an empty tier list, removes the fast tier, or adjusts thresholds, the function silently falls back to `0`. Consequently, `estimateFee` and `transfer()` price fast transfers as free, risking protocol underpayment or on-chain revert at settlement. Additionally, it throws a generic `Error` on network errors rather than `IrisRequestError`.

### Implementation Patch

```typescript
// diff --git a/src/errors.ts b/src/errors.ts
export class IrisRequestError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = 'IrisRequestError';
  }
}

export class IrisFastTierUnavailableError extends Error {
  constructor(message = 'No Fast Transfer tier is currently offered by Iris API.') {
    super(message);
    this.name = 'IrisFastTierUnavailableError';
  }
}
```

```typescript
// diff --git a/src/iris/poll.ts b/src/iris/poll.ts
import { IrisRequestError, IrisFastTierUnavailableError } from '../errors';

export async function fetchFastTransferFeeBps(irisApiUrl: string): Promise<number> {
  const res = await fetch(`${irisApiUrl}/fees/fast`);
  if (!res.ok) {
    throw new IrisRequestError(
      `Iris fee endpoint failed with HTTP ${res.status}: ${res.statusText}`,
      res.status
    );
  }

  const body = (await res.json()) as Array<{ finalityThreshold: number; minimumFee?: number }>;
  const fastEntry = body.find((entry) => entry.finalityThreshold <= 1000);

  if (!fastEntry || fastEntry.minimumFee === undefined) {
    throw new IrisFastTierUnavailableError(
      `Iris returned no eligible fast tier with finalityThreshold <= 1000. ` +
      `Received tiers: ${JSON.stringify(body)}`
    );
  }

  return fastEntry.minimumFee;
}
```

### Unit Verification Tests (`test/iris-fee-pricing.test.ts`)

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchFastTransferFeeBps } from '../src/iris/poll';
import { IrisRequestError, IrisFastTierUnavailableError } from '../src/errors';

describe('fetchFastTransferFeeBps pricing validation', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('throws IrisRequestError with status on HTTP error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable'
    }));

    await expect(fetchFastTransferFeeBps('https://iris.example.com'))
      .rejects.toThrow(IrisRequestError);
  });

  it('throws IrisFastTierUnavailableError when fast tier is missing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue([{ finalityThreshold: 5000, minimumFee: 50 }]) // Only slow tier
    }));

    await expect(fetchFastTransferFeeBps('https://iris.example.com'))
      .rejects.toThrow(IrisFastTierUnavailableError);
  });

  it('correctly returns fee when fast tier is present', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue([{ finalityThreshold: 800, minimumFee: 15 }])
    }));

    const fee = await fetchFastTransferFeeBps('https://iris.example.com');
    expect(fee).toBe(15);
  });
});
```
