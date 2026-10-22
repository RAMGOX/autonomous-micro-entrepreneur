# Solution: [Bounty: $90] Make estimateFee agree with transfer() on maxFee and maxWait fallback
- **Issue:** [Parabola-org/parabola #7](https://github.com/Parabola-org/parabola/issues/7) / [bounty-plaza #1909](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1909)
- **Bounty:** $90 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Root Cause Analysis
In `src/estimate.ts`, `estimateFee()` returns a fast quote whenever the endpoint reports fast transfers are supported, ignoring `maxFee` and `maxWait` parameters. In contrast, `transfer()` in `src/transfer.ts` compares the quoted fee against `options.maxFee` and duration against `options.maxWait`, silently downgrading the transfer mode to `standard` when constraints are exceeded. As a result, users receive a fast quote during pre-flight estimation but execute a standard transfer during execution.

### Implementation Patch

```typescript
// diff --git a/src/utils/fee.ts b/src/utils/fee.ts
export interface FeeFallbackParams {
  maxFee?: bigint;
  maxWaitSec?: number;
}

export function evaluateTransferTier(
  fastFeeRaw: bigint,
  standardFeeRaw: bigint,
  params: FeeFallbackParams
): { mode: 'fast' | 'standard'; feeRaw: bigint } {
  const FAST_ESTIMATED_DURATION_SEC = 15;

  if (params.maxFee !== undefined && fastFeeRaw > params.maxFee) {
    return { mode: 'standard', feeRaw: standardFeeRaw };
  }

  if (params.maxWaitSec !== undefined && FAST_ESTIMATED_DURATION_SEC > params.maxWaitSec) {
    return { mode: 'standard', feeRaw: standardFeeRaw };
  }

  return { mode: 'fast', feeRaw: fastFeeRaw };
}
```

```typescript
// diff --git a/src/estimate.ts b/src/estimate.ts
import { evaluateTransferTier } from './utils/fee';

export interface EstimateFeeParams {
  sourceChain: string;
  destinationChain: string;
  amount: string;
  maxFee?: bigint;
  maxWait?: number;
}

export async function estimateFee(params: EstimateFeeParams) {
  const standardFeeRaw = 0n;
  const fastFeeBps = await fetchFastTransferFeeBps(IRIS_API_URL);
  const fastFeeRaw = calculateFee(params.amount, fastFeeBps);

  const tier = evaluateTransferTier(fastFeeRaw, standardFeeRaw, {
    maxFee: params.maxFee,
    maxWaitSec: params.maxWait,
  });

  return {
    mode: tier.mode,
    feeRaw: tier.feeRaw,
    estimatedDurationSec: tier.mode === 'fast' ? 15 : 300,
  };
}
```

### Unit Verification Tests (`test/estimate-fee-fallback.test.ts`)

```typescript
import { describe, it, expect, vi } from 'vitest';
import { estimateFee } from '../src/estimate';
import * as irisModule from '../src/iris/poll';

describe('estimateFee fallback agreement with transfer()', () => {
  it('quotes fast mode when fee and wait are within constraints', async () => {
    vi.spyOn(irisModule, 'fetchFastTransferFeeBps').mockResolvedValue(10); // 10 bps

    const quote = await estimateFee({
      sourceChain: 'arc',
      destinationChain: 'stellar',
      amount: '1000',
      maxFee: 500000n, // Covers fee
      maxWait: 30,     // Allows 15s fast transfer
    });

    expect(quote.mode).toBe('fast');
  });

  it('falls back to standard quote when fast fee exceeds maxFee', async () => {
    vi.spyOn(irisModule, 'fetchFastTransferFeeBps').mockResolvedValue(100);

    const quote = await estimateFee({
      sourceChain: 'arc',
      destinationChain: 'stellar',
      amount: '1000',
      maxFee: 10n, // Lower than quoted fee
      maxWait: 30,
    });

    expect(quote.mode).toBe('standard');
    expect(quote.feeRaw).toBe(0n);
  });

  it('falls back to standard quote when maxWait < 15 seconds', async () => {
    vi.spyOn(irisModule, 'fetchFastTransferFeeBps').mockResolvedValue(10);

    const quote = await estimateFee({
      sourceChain: 'arc',
      destinationChain: 'stellar',
      amount: '1000',
      maxWait: 5, // Requires response in 5s; fast takes 15s
    });

    expect(quote.mode).toBe('standard');
  });
});
```
