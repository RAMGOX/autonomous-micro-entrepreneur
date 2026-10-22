# Solution: [Bounty: $90] Reject unsupported CCTP message versions in decodeCctpMessage
- **Issue:** [Parabola-org/parabola #9](https://github.com/Parabola-org/parabola/issues/9) / [bounty-plaza #1907](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1907)
- **Bounty:** $90 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Root Cause Analysis
In `src/utils/message.ts`, `decodeCctpMessage` validates byte length but bypasses protocol version checks on the CCTP message header (`version` at bytes 0..4) and burn body header (`burnBodyVersion` at body offset 0..4). If Circle deploys a new message format (e.g. V3) with modified field alignments, or non-burn message bodies reach this parser, the decoder reads invalid amounts and recipients without raising an error.

### Implementation Patch

```typescript
// diff --git a/src/errors.ts b/src/errors.ts
export class UnsupportedCctpVersionError extends Error {
  constructor(public readonly foundVersion: number, public readonly supported: number[]) {
    super(
      `Unsupported CCTP message version ${foundVersion}. Supported versions: ${supported.join(', ')}.`
    );
    this.name = 'UnsupportedCctpVersionError';
  }
}
```

```typescript
// diff --git a/src/utils/message.ts b/src/utils/message.ts
import { UnsupportedCctpVersionError } from '../errors';

export const SUPPORTED_CCTP_MESSAGE_VERSIONS = [0];
export const SUPPORTED_BURN_BODY_VERSIONS = [0];

export function decodeCctpMessage(messageHex: string) {
  const bytes = Buffer.from(messageHex.replace(/^0x/, ''), 'hex');
  if (bytes.length < 132) {
    throw new Error(`CCTP message too short: expected >= 132 bytes, got ${bytes.length}`);
  }

  // 1. Validate header message version (bytes 0..4)
  const messageVersion = bytes.readUInt32BE(0);
  if (!SUPPORTED_CCTP_MESSAGE_VERSIONS.includes(messageVersion)) {
    throw new UnsupportedCctpVersionError(messageVersion, SUPPORTED_CCTP_MESSAGE_VERSIONS);
  }

  // 2. Validate burn message body version (header is 116 bytes, body version is first 4 bytes of body)
  const burnBodyVersion = bytes.readUInt32BE(116);
  if (!SUPPORTED_BURN_BODY_VERSIONS.includes(burnBodyVersion)) {
    throw new UnsupportedCctpVersionError(burnBodyVersion, SUPPORTED_BURN_BODY_VERSIONS);
  }

  // Proceed with safe extraction at confirmed offsets
  const sourceDomain = bytes.readUInt32BE(4);
  const destinationDomain = bytes.readUInt32BE(8);
  const nonce = bytes.readBigUInt64BE(12);
  const sender = '0x' + bytes.subarray(20, 52).toString('hex');
  const recipient = '0x' + bytes.subarray(52, 84).toString('hex');
  const destinationCaller = '0x' + bytes.subarray(84, 116).toString('hex');

  const burnToken = '0x' + bytes.subarray(120, 152).toString('hex');
  const mintRecipient = '0x' + bytes.subarray(152, 184).toString('hex');
  const amount = BigInt('0x' + bytes.subarray(184, 216).toString('hex'));

  return {
    version: messageVersion,
    sourceDomain,
    destinationDomain,
    nonce,
    sender,
    recipient,
    destinationCaller,
    burnBodyVersion,
    burnToken,
    mintRecipient,
    amount,
  };
}
```

### Unit Verification Tests (`test/cctp-message-version.test.ts`)

```typescript
import { describe, it, expect } from 'vitest';
import { decodeCctpMessage } from '../src/utils/message';
import { UnsupportedCctpVersionError } from '../src/errors';

describe('decodeCctpMessage version validation', () => {
  it('rejects unsupported top-level message version', () => {
    // Construct mock 132-byte message with version 99 at byte 0
    const buf = Buffer.alloc(216);
    buf.writeUInt32BE(99, 0); // Invalid message version
    buf.writeUInt32BE(0, 116); // Valid body version

    expect(() => decodeCctpMessage('0x' + buf.toString('hex')))
      .toThrow(UnsupportedCctpVersionError);
  });

  it('rejects unsupported burn body version', () => {
    // Construct mock 132-byte message with valid version 0 but body version 99
    const buf = Buffer.alloc(216);
    buf.writeUInt32BE(0, 0); // Valid message version
    buf.writeUInt32BE(99, 116); // Invalid body version

    expect(() => decodeCctpMessage('0x' + buf.toString('hex')))
      .toThrow(UnsupportedCctpVersionError);
  });

  it('decodes successfully when versions match supported schema', () => {
    const buf = Buffer.alloc(216);
    buf.writeUInt32BE(0, 0);   // Version 0
    buf.writeUInt32BE(0, 116); // Body version 0
    buf.writeUInt32BE(1, 4);   // sourceDomain
    buf.writeUInt32BE(7, 8);   // destinationDomain

    const decoded = decodeCctpMessage('0x' + buf.toString('hex'));
    expect(decoded.version).toBe(0);
    expect(decoded.burnBodyVersion).toBe(0);
    expect(decoded.sourceDomain).toBe(1);
    expect(decoded.destinationDomain).toBe(7);
  });
});
```
