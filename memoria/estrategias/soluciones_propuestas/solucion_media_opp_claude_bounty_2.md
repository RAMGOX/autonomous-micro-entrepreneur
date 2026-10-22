# Solution: [BOUNTY $75] TEMPLATE: CLAUDE.md for a Next.js + SQLite SaaS project
- **Issue:** [claude-builders-bounty/claude-builders-bounty #2](https://github.com/claude-builders-bounty/claude-builders-bounty/issues/2)
- **Bounty:** $75 USD (powered by Opire)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## Production-Ready `CLAUDE.md` Template

```markdown
# SaaS Development Guidelines: Next.js 15 (App Router) + SQLite (better-sqlite3 / Drizzle)

## 1. Project Philosophy & Core Stack
- **Framework:** Next.js 15 (React 19, App Router exclusively).
- **Database:** SQLite with WAL mode enabled (`better-sqlite3` locally, Turso for edge/distributed read replicas).
- **ORM:** Drizzle ORM for zero-overhead, type-safe queries.
- **Styling:** Tailwind CSS + Radix UI primitives.
- **Rule:** Simplicity first. Avoid microservices or third-party wrappers when native Next.js features suffice.

---

## 2. Standard Commands
- `npm run dev`: Starts local Next.js dev server with Turbo (`next dev --turbopack`).
- `npm run db:generate`: Generates SQL migrations from `src/db/schema.ts`.
- `npm run db:migrate`: Applies migrations against the SQLite database file (`data/saas.db`).
- `npm run db:studio`: Launches Drizzle Studio viewer at `https://local.drizzle.studio`.
- `npm test`: Runs vitest suites for server actions and utility logic.
- `npm run lint`: Strict ESLint + TypeScript verification.

---

## 3. Database & SQLite Operational Rules
1. **WAL Mode is Mandatory:**
   ```typescript
   // src/db/client.ts
   import Database from 'better-sqlite3';
   import { drizzle } from 'drizzle-orm/better-sqlite3';
   const sqlite = new Database(process.env.DATABASE_PATH || './data/saas.db');
   sqlite.pragma('journal_mode = WAL');
   sqlite.pragma('busy_timeout = 5000');
   sqlite.pragma('foreign_keys = ON');
   export const db = drizzle(sqlite);
   ```
2. **Schema Organization:**
   - Define all models in `src/db/schema/` grouped by domain (`auth.ts`, `teams.ts`, `subscriptions.ts`).
   - Re-export everything from `src/db/schema/index.ts`.
3. **Migration Integrity:**
   - Never edit existing migration files in `drizzle/`.
   - Never run raw `ALTER TABLE` manually; always use Drizzle kit.

---

## 4. Architecture & Coding Patterns
- **Server Actions for Mutations:** Put mutations in `src/actions/[domain].ts`. Validate all payloads using Zod before touching the database.
- **Server Components for Reads:** Data fetching occurs directly in React Server Components via Drizzle. Do not invent REST endpoints (`/api/get-users`) for internal views.
- **Auth Guards:** Every Server Action mutating customer data must call `const session = await requireAuth();` as the first instruction.
- **Error Boundaries:** Export `error.tsx` and `loading.tsx` in every route folder.

---

## 5. Anti-Patterns (Strictly Prohibited)
- ❌ **No `useEffect` for data fetching:** Fetch directly in Server Components.
- ❌ **No raw in-memory SQLite locks:** Always rely on SQLite's native WAL + `busy_timeout`.
- ❌ **No unbounded queries:** Always add `.limit()` to `.select()` queries.
- ❌ **No secret leaking:** Never prefix backend SQLite configuration with `NEXT_PUBLIC_`.
```
