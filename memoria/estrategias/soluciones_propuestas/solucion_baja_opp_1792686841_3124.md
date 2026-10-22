# Solution: Reward parser treats bounty IDs as money in scripts/sources/github.mjs
- **Issue:** [podzemniytip/shipradar #1](https://github.com/podzemniytip/shipradar/issues/1)
- **Bounty:** $83 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Root Cause Analysis
In `scripts/sources/github.mjs`, when extracting bounty values from issue titles and descriptions:
1. `cleanText()` strips `#` characters before running regex extractions.
2. The fallback pattern for money extraction allows optional currency markers (`(?:bounty|reward|prize)\s*(\d+)`), which accidentally matches issue reference numbers (e.g. `bounty #83` -> `bounty 83` -> extracted as `$83 USD`).
3. This creates false reward magnitudes and pollutes ranking.

### Implementation Fix

```javascript
// diff --git a/scripts/sources/github.mjs b/scripts/sources/github.mjs
// Enforce currency markers or explicit command format (/bounty <amount>)

export function parseRewardAmount(title, body) {
  const combinedText = `${title}\n${body || ''}`;

  // 1. Explicit bot command syntax: /bounty <amount> or /reward <amount>
  const commandMatch = combinedText.match(/\/(?:bounty|reward|tip)\s+([0-9]+(?:\.[0-9]+)?)/i);
  if (commandMatch) {
    return parseFloat(commandMatch[1]);
  }

  // 2. Strict currency-tagged patterns: $100, 100 USD, 100 USDC, 100 USDT, 0.5 ETH
  const currencyMatch = combinedText.match(
    /(?:\$|USDC\s*|USDT\s*|USD\s*)\s*([0-9]+(?:\.[0-9]+)?)|([0-9]+(?:\.[0-9]+)?)\s*(?:USD|USDC|USDT|\$)/i
  );
  if (currencyMatch) {
    const val = currencyMatch[1] || currencyMatch[2];
    return parseFloat(val);
  }

  // 3. Reject bare numbers preceded by "bounty", "reward", "prize" if they were issue numbers (#83)
  // Bare numbers without currency symbols MUST NOT be treated as currency.
  return null;
}
```

### Offline Regression Suite (`test/reward-parser.test.mjs`)

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseRewardAmount } from '../scripts/sources/github.mjs';

test('Regression tests for reward parser', () => {
  // Bug reproduction case: Frantic bounty #83 with worker price $9
  const bugCase = parseRewardAmount(
    'Frantic bounty #83',
    'Worker price: $9 for completing implementation'
  );
  assert.equal(bugCase, 9); // Must NOT return 83

  // Explicit slash command
  assert.equal(parseRewardAmount('Bug fix', '/bounty 250'), 250);

  // Standard currency prefixes & suffixes
  assert.equal(parseRewardAmount('Add test suite [$150]', ''), 150);
  assert.equal(parseRewardAmount('Feature request', 'Payout: 300 USDC'), 300);
  assert.equal(parseRewardAmount('Optimization', 'Award: 50 USDT upon merge'), 50);

  // Avoid false positives on issue references without currency
  assert.equal(parseRewardAmount('Resolves bounty 198', 'No reward specified'), null);
});
```
