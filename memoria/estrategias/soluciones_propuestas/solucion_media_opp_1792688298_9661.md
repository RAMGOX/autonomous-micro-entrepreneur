# Solution: [Bounty: $105] Preserve burnTxHash when Stellar confirmation polling hits transient RPC errors
- **Issue:** [Parabola-org/parabola #1](https://github.com/Parabola-org/parabola/issues/1) / [bounty-plaza #1915](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1915)
- **Bounty:** $105 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Root Cause Analysis
In `src/chains/stellar.ts`, `pollTransactionStatus` calls `server.getTransaction(hash)` in a `while` loop. While `SubmissionTimeoutError` preserves `hash` upon timeout, an unhandled transient network error (e.g., Soroban RPC connection reset or 503) causes an immediate unhandled promise rejection without the transaction hash. Because the burn transaction was already submitted to the network, losing `hash` strips the caller of the only key needed for reconciliation and mint completion.

### Implementation Patch

```typescript
// diff --git a/src/errors.ts b/src/errors.ts
export class TransactionPollingError extends Error {
  constructor(message: string, public readonly hash: string, public readonly cause?: unknown) {
    super(message);
    this.name = 'TransactionPollingError';
  }
}
```

```typescript
// diff --git a/src/chains/stellar.ts b/src/chains/stellar.ts
import { SubmissionTimeoutError, TransactionPollingError } from '../errors';

export async function pollTransactionStatus(
  server: any,
  hash: string,
  options: { timeoutMs?: number; pollIntervalMs?: number; maxConsecutiveErrors?: number } = {}
) {
  const { timeoutMs = 60000, pollIntervalMs = 2000, maxConsecutiveErrors = 5 } = options;
  const deadline = Date.now() + timeoutMs;
  let consecutiveErrors = 0;

  while (Date.now() < deadline) {
    try {
      const response = await server.getTransaction(hash);
      consecutiveErrors = 0; // reset counter on successful RPC contact

      if (response.status === 'SUCCESS') {
        return response;
      }
      if (response.status === 'FAILED') {
        throw new Error(`Transaction ${hash} failed on-chain: ${JSON.stringify(response.resultXdr)}`);
      }
    } catch (err: any) {
      if (err.message?.includes('failed on-chain')) {
        throw err;
      }

      consecutiveErrors++;
      if (consecutiveErrors >= maxConsecutiveErrors) {
        throw new TransactionPollingError(
          `RPC failed ${consecutiveErrors} consecutive times while polling transaction ${hash}: ${err.message}`,
          hash,
          err
        );
      }
    }

    await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
  }

  throw new SubmissionTimeoutError(`Timed out polling status for transaction ${hash}`, hash);
}
```

### Unit Verification Tests (`test/stellar-poll-hash-preservation.test.ts`)

```typescript
import { describe, it, expect, vi } from 'vitest';
import { pollTransactionStatus } from '../src/chains/stellar';
import { TransactionPollingError } from '../src/errors';

describe('pollTransactionStatus hash preservation', () => {
  it('preserves hash on persistent transient RPC errors', async () => {
    const serverMock = {
      getTransaction: vi.fn().mockRejectedValue(new Error('503 Service Unavailable')),
    };

    try {
      await pollTransactionStatus(serverMock, '0xstellarburnhash123', {
        timeoutMs: 10000,
        pollIntervalMs: 50,
        maxConsecutiveErrors: 3
      });
      expect.fail('Should have thrown TransactionPollingError');
    } catch (err: any) {
      expect(err).toBeInstanceOf(TransactionPollingError);
      expect(err.hash).toBe('0xstellarburnhash123');
    }
  });

  it('absorbs intermittent RPC errors and succeeds once RPC recovers', async () => {
    let attempts = 0;
    const serverMock = {
      getTransaction: vi.fn().mockImplementation(async () => {
        attempts++;
        if (attempts <= 2) throw new Error('Network glitch');
        return { status: 'SUCCESS', resultXdr: 'AAAA' };
      }),
    };

    const res = await pollTransactionStatus(serverMock, '0xstellarburnhash123', {
      timeoutMs: 10000,
      pollIntervalMs: 50,
      maxConsecutiveErrors: 5
    });

    expect(res.status).toBe('SUCCESS');
    expect(attempts).toBe(3);
  });
});
```
