# Solution: Reject amounts whose precision exceeds destination chain USDC decimals
- **Issue:** [Parabola-org/parabola #10](https://github.com/Parabola-org/parabola/issues/10) / [bounty-plaza #1906](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1906)
- **Bounty:** $90 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Analysis & Problem Statement
Arc USDC has 6 decimals, Stellar USDC has 7. When transferring between chains of unequal decimals (e.g. Stellar -> Arc), `transfer()` parses the amount using only the source chain's decimals. An amount like `"1.1234567"` parses validly on Stellar (7 decimals) and burns 11,234,567 units, but the destination mint truncates or rejects excess precision silently on-chain. Pre-flight validation must reject inputs whose fractional digits exceed the destination chain's decimal capacity prior to initiating burns.

### Implementation Patch

```typescript
// diff --git a/src/utils/amount.ts b/src/utils/amount.ts
export const CHAIN_USDC_DECIMALS: Record<string, number> = {
  arc: 6,
  ethereum: 6,
  base: 6,
  arbitrum: 6,
  stellar: 7,
};

export function validateTransferPrecision(amountStr: string, destinationChain: string): void {
  const destDecimals = CHAIN_USDC_DECIMALS[destinationChain.toLowerCase()];
  if (destDecimals === undefined) {
    throw new Error(`Unsupported destination chain: ${destinationChain}`);
  }

  const parts = amountStr.split('.');
  if (parts.length === 2) {
    const decimals = parts[1].replace(/0+$/, ''); // trim trailing zeros
    if (decimals.length > destDecimals) {
      throw new Error(
        `Precision error: Amount "${amountStr}" has ${decimals.length} decimal places, ` +
        `but destination chain "${destinationChain}" only supports up to ${destDecimals} decimals.`
      );
    }
  }
}
```

```typescript
// diff --git a/src/transfer.ts b/src/transfer.ts
import { validateTransferPrecision } from './utils/amount';

export async function transfer(
  sourceChain: string,
  destinationChain: string,
  amount: string,
  recipient: string
) {
  // Pre-flight check before initiating any burn or allowance writes
  validateTransferPrecision(amount, destinationChain);

  // Continue standard transfer lifecycle
  return await initiateBridgeTransfer(sourceChain, destinationChain, amount, recipient);
}
```

### Unit Verification Tests (`test/precision-validation.test.ts`)

```typescript
import { describe, it, expect } from 'vitest';
import { validateTransferPrecision } from '../src/utils/amount';

describe('validateTransferPrecision pre-flight checks', () => {
  it('allows amounts with decimal precision within destination limit', () => {
    // 6 decimals to Arc (supports 6) -> valid
    expect(() => validateTransferPrecision('1.123456', 'arc')).not.toThrow();
    // 2 decimals to Arc -> valid
    expect(() => validateTransferPrecision('10.50', 'arc')).not.toThrow();
    // Integer amount -> valid
    expect(() => validateTransferPrecision('100', 'arc')).not.toThrow();
    // 7 decimals to Stellar (supports 7) -> valid
    expect(() => validateTransferPrecision('1.1234567', 'stellar')).not.toThrow();
  });

  it('allows trailing zeros exceeding decimal limit', () => {
    // 1.1200000 has 2 significant decimals, valid on 6-decimal chain
    expect(() => validateTransferPrecision('1.1200000', 'arc')).not.toThrow();
  });

  it('rejects amounts with significant decimals exceeding destination limit', () => {
    // 7 decimals to Arc (supports 6) -> throws
    expect(() => validateTransferPrecision('1.1234567', 'arc')).toThrow(
      /Precision error: Amount "1.1234567" has 7 decimal places, but destination chain "arc" only supports up to 6 decimals/
    );
  });
});
```
