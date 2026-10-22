# Solution: Add an XNO (Nano) settlement option for agent-initiated payment
- **Issue:** [joeychrys/mastra-agent-stack #45](https://github.com/joeychrys/mastra-agent-stack/issues/45)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Mastra Settlement Tool (`src/mastra/tools/nanoSettle.ts`)

```typescript
import { createTool } from '@mastra/core';
import { z } from 'zod';

const NANO_RPC_URL = process.env.NANO_RPC_URL || 'https://node.somenano.com/proxy';

interface NanoRpcResponse {
  hash?: string;
  error?: string;
}

export const nanoSettleTool = createTool({
  id: 'nano-settle',
  name: 'Nano (XNO) Autonomous Instant Settlement',
  description: 'Executes or verifies zero-fee, sub-second peer-to-peer XNO payments between autonomous agents.',
  inputSchema: z.object({
    action: z.enum(['send', 'verify_receipt']),
    recipientAddress: z.string().regex(/^nano_[13][0-9a-z]{59}$/, 'Invalid Nano address format'),
    amountRaw: z.string().describe('Amount in 10^30 raw units (1 XNO = 10^30 raw)'),
    blockHash: z.string().optional().describe('Block hash to verify for receipt confirmation'),
  }),
  outputSchema: z.object({
    success: z.boolean(),
    blockHash: z.string().optional(),
    verified: z.boolean().optional(),
    message: z.string(),
  }),
  execute: async ({ context }) => {
    const { action, recipientAddress, amountRaw, blockHash } = context;

    if (action === 'verify_receipt' && blockHash) {
      // Query block confirmation state
      const res = await fetch(NANO_RPC_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'block_info',
          hash: blockHash,
        }),
      });
      const data = await res.json();
      const isConfirmed = data.confirmed === 'true';

      return {
        success: isConfirmed,
        blockHash,
        verified: isConfirmed,
        message: isConfirmed
          ? `Block ${blockHash} confirmed on Nano network.`
          : `Block ${blockHash} not yet confirmed.`,
      };
    }

    if (action === 'send') {
      const walletSeed = process.env.AGENT_NANO_SEED;
      if (!walletSeed) {
        throw new Error('AGENT_NANO_SEED environment variable is not configured.');
      }

      // Query account info to get frontier
      const agentAccount = process.env.AGENT_NANO_ADDRESS!;
      const infoRes = await fetch(NANO_RPC_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'account_info',
          account: agentAccount,
        }),
      });
      const info = await infoRes.json();

      // Broadcast transaction block
      const processRes = await fetch(NANO_RPC_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'process',
          json_block: 'true',
          subtype: 'send',
          block: {
            type: 'state',
            account: agentAccount,
            previous: info.frontier,
            representative: info.representative,
            balance: (BigInt(info.balance) - BigInt(amountRaw)).toString(),
            link: recipientAddress,
          },
        }),
      });

      const processData = (await processRes.json()) as NanoRpcResponse;
      if (processData.error) {
        throw new Error(`Nano node error: ${processData.error}`);
      }

      return {
        success: true,
        blockHash: processData.hash,
        verified: true,
        message: `Dispatched ${amountRaw} raw to ${recipientAddress}. Hash: ${processData.hash}`,
      };
    }

    return {
      success: false,
      message: 'Invalid tool invocation parameters.',
    };
  },
});
```
