# Solution: [Bounty: $105] checkStellarRecipientReady must not report RPC outages as missing accounts
- **Issue:** [Parabola-org/parabola #4](https://github.com/Parabola-org/parabola/issues/4) / [bounty-plaza #1912](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1912)
- **Bounty:** $105 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Root Cause Analysis
In `src/chains/stellar.ts`, `checkStellarRecipientReady` wraps `server.getAccount(recipient)` in a bare `catch` block that unconditionally returns:
```typescript
return { exists: false, hasTrustline: false, ready: false };
```
When Stellar RPC endpoints experience rate limiting (HTTP 429) or transient outages (503 / network drops), this swallows the infrastructure fault and makes `assertStellarRecipientReady` in `src/transfer.ts` fail with:
> *"recipient does not exist yet. It must be funded with at least the minimum XLM reserve"*
This misleads callers into thinking their destination account address is uncreated, when in fact the RPC server failed.

### Implementation Patch

```typescript
// diff --git a/src/chains/stellar.ts b/src/chains/stellar.ts
export class StellarRpcError extends Error {
  constructor(message: string, public readonly originalError: unknown) {
    super(message);
    this.name = 'StellarRpcError';
  }
}

export function isAccountNotFoundError(err: any): boolean {
  return err?.response?.status === 404 || err?.name === 'NotFoundError';
}

export async function checkStellarRecipientReady(
  server: any,
  recipient: string,
  assetCode = 'USDC'
): Promise<{ exists: boolean; hasTrustline: boolean; ready: boolean }> {
  try {
    const account = await server.getAccount(recipient);
    const hasTrustline = account.balances.some(
      (b: any) => b.asset_code === assetCode
    );
    return {
      exists: true,
      hasTrustline,
      ready: hasTrustline,
    };
  } catch (err: any) {
    // ONLY 404 means account genuinely does not exist on-chain
    if (isAccountNotFoundError(err)) {
      return { exists: false, hasTrustline: false, ready: false };
    }

    // Any other error (429 rate limit, 503 unavailable, network timeout) must be rethrown
    throw new StellarRpcError(
      `Stellar RPC request failed while checking recipient status: ${err?.message || err}`,
      err
    );
  }
}
```

### Unit Verification Tests (`test/stellar-recipient-ready.test.ts`)

```typescript
import { describe, it, expect, vi } from 'vitest';
import { checkStellarRecipientReady, StellarRpcError } from '../src/chains/stellar';

describe('checkStellarRecipientReady error discrimination', () => {
  it('returns exists: false on 404 NotFound error', async () => {
    const serverMock = {
      getAccount: vi.fn().mockRejectedValue({ response: { status: 404 }, name: 'NotFoundError' }),
    };

    const res = await checkStellarRecipientReady(serverMock, 'GACCOUNT404');
    expect(res).toEqual({ exists: false, hasTrustline: false, ready: false });
  });

  it('throws StellarRpcError on 429 rate-limiting outage', async () => {
    const serverMock = {
      getAccount: vi.fn().mockRejectedValue({ response: { status: 429, statusText: 'Too Many Requests' } }),
    };

    await expect(checkStellarRecipientReady(serverMock, 'GACCOUNTRATE'))
      .rejects.toThrow(StellarRpcError);
  });

  it('throws StellarRpcError on 503 RPC downtime', async () => {
    const serverMock = {
      getAccount: vi.fn().mockRejectedValue(new Error('Connection reset by peer')),
    };

    await expect(checkStellarRecipientReady(serverMock, 'GACCOUNTDOWN'))
      .rejects.toThrow(StellarRpcError);
  });
});
```
