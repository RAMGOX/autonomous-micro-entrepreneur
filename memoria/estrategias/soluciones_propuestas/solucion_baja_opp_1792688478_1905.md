# Solution: [Bounty: $90] Add ESLint with typescript-eslint and wire it into CI
- **Issue:** [Parabola-org/parabola #11](https://github.com/Parabola-org/parabola/issues/11) / [bounty-plaza #1905](https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/1905)
- **Bounty:** $90 USD
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Analysis & Problem Statement
The codebase CI runs unit tests and build checks, but lacks static analysis. Issues such as unhandled floating promises in asynchronous polling loops (`pollForAttestation`), unsafe `any` casts, and unused imports pass CI without warning.

### Implementation Patch

```json
// diff --git a/package.json b/package.json
{
  "scripts": {
    "test": "vitest run",
    "build": "tsup",
    "typecheck": "tsc --noEmit",
    "lint": "eslint . --ext .ts",
    "lint:fix": "eslint . --ext .ts --fix"
  },
  "devDependencies": {
    "@typescript-eslint/eslint-plugin": "^7.18.0",
    "@typescript-eslint/parser": "^7.18.0",
    "eslint": "^8.57.0"
  }
}
```

```javascript
// diff --git a/.eslintrc.cjs b/.eslintrc.cjs
// new file mode 100644
module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {
    project: './tsconfig.json',
    tsconfigRootDir: __dirname,
    ecmaVersion: 2022,
    sourceType: 'module',
  },
  plugins: ['@typescript-eslint'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:@typescript-eslint/recommended-requiring-type-checking',
  ],
  rules: {
    '@typescript-eslint/no-floating-promises': 'error',
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    '@typescript-eslint/consistent-type-imports': ['error', { prefer: 'type-imports' }],
    'no-console': ['warn', { allow: ['warn', 'error', 'info'] }],
  },
  ignorePatterns: ['dist/', 'node_modules/', '*.config.*'],
};
```

```yaml
// diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'
      - run: npm ci
      - name: ESLint Static Analysis
        run: npm run lint
      - name: Typecheck
        run: npm run typecheck
      - name: Unit Tests
        run: npm test
      - name: Production Build
        run: npm run build
```
