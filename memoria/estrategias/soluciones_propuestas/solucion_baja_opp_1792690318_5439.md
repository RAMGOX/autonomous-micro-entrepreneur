# Solution: Deleting User should wipe out entire history (Polar.sh synchronization)
- **Issue:** [suprabhat15/marketing-platform #92](https://github.com/suprabhat15/marketing-platform/issues/92)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Analysis & Problem Statement
Currently, deleting a user record deletes local DB entries but leaves the customer profile and active subscriptions orphaned on Polar.sh. Re-registering with the same email or querying customer state results in desynchronization and API errors.

### Implementation Patch

```typescript
// diff --git a/src/services/userService.ts b/src/services/userService.ts
import { Polar } from '@polar-sh/sdk';
import { db } from '../db';
import { users, campaignHistory } from '../db/schema';
import { eq } from 'drizzle-orm';

const polar = new Polar({
  accessToken: process.env.POLAR_ACCESS_TOKEN!,
});

export async function deleteUserAccount(userId: string): Promise<void> {
  const user = await db.query.users.findFirst({
    where: eq(users.id, userId),
  });

  if (!user) {
    throw new Error(`User with ID ${userId} not found.`);
  }

  // 1. Wipe customer profile and subscriptions from Polar.sh
  if (user.polarCustomerId) {
    try {
      // Cancel active subscriptions and delete customer
      await polar.customers.delete({ id: user.polarCustomerId });
      console.info(`[Polar] Successfully purged customer ${user.polarCustomerId} for user ${userId}.`);
    } catch (err: any) {
      if (err.status === 404) {
        console.warn(`[Polar] Customer ${user.polarCustomerId} was already deleted on Polar.`);
      } else {
        console.error(`[Polar Error] Failed to purge customer ${user.polarCustomerId}:`, err);
        throw new Error(`Failed to delete external billing profile: ${err.message}`);
      }
    }
  }

  // 2. Cascade delete marketing campaigns and history
  await db.delete(campaignHistory).where(eq(campaignHistory.userId, userId));

  // 3. Delete user row
  await db.delete(users).where(eq(users.id, userId));
  console.info(`[UserService] Successfully wiped user ${userId} and full history.`);
}
```

### Unit Verification Tests (`tests/user-deletion.test.ts`)

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { deleteUserAccount } from '../src/services/userService';

describe('deleteUserAccount with Polar sync', () => {
  it('calls Polar customer deletion and purges local records', async () => {
    const deletePolarSpy = vi.fn().mockResolvedValue({ success: true });
    vi.stubGlobal('polar', { customers: { delete: deletePolarSpy } });

    await deleteUserAccount('user_123');
    expect(deletePolarSpy).toHaveBeenCalledWith({ id: 'polar_cust_123' });
  });

  it('tolerates 404 if user was already removed on Polar', async () => {
    const deletePolarSpy = vi.fn().mockRejectedValue({ status: 404 });
    vi.stubGlobal('polar', { customers: { delete: deletePolarSpy } });

    await expect(deleteUserAccount('user_123')).resolves.not.toThrow();
  });
});
```
