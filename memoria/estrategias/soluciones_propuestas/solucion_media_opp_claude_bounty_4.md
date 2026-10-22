# Solution: [BOUNTY $150] AGENT: Claude Code sub-agent that reviews a PR and posts a structured comment
- **Issue:** [claude-builders-bounty/claude-builders-bounty #4](https://github.com/claude-builders-bounty/claude-builders-bounty/issues/4)
- **Bounty:** $150 USD (powered by Opire)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. CLI Reviewer Engine (`bin/claude-review.js`)

```javascript
#!/usr/bin/env node
import { execSync } from 'node:child_process';
import https from 'node:https';

const args = process.argv.slice(2);
const prIndex = args.indexOf('--pr');
if (prIndex === -1 || !args[prIndex + 1]) {
  console.error('Usage: claude-review --pr https://github.com/:owner/:repo/pull/:id');
  process.exit(1);
}

const prUrl = args[prIndex + 1];
const match = prUrl.match(/github\.com\/([^\/]+)\/([^\/]+)\/pull\/(\d+)/);
if (!match) {
  console.error('Error: Invalid PR URL format.');
  process.exit(1);
}

const [, owner, repo, pullNumber] = match;
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;

async function fetchDiff() {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.github.com',
      path: `/repos/${owner}/${repo}/pulls/${pullNumber}`,
      headers: {
        'User-Agent': 'claude-pr-reviewer',
        'Accept': 'application/vnd.github.v3.diff',
        ...(GITHUB_TOKEN ? { 'Authorization': `Bearer ${GITHUB_TOKEN}` } : {})
      }
    };
    https.get(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

async function runReview() {
  const diff = await fetchDiff();
  if (!diff || diff.length === 0) {
    console.log('No diff found for review.');
    return;
  }

  const reviewPrompt = `You are a Senior Security & Performance Code Reviewer. Analyze the following pull request diff and produce a structured Markdown review:

### Diff:
${diff.slice(0, 15000)}

Output must follow this exact format:
## Automated Code Review Summary
### 1. Summary of Changes
[2-3 concise sentences explaining the intent and impact]

### 2. Identified Risks & Vulnerabilities
- [Risk 1 or None]
- [Risk 2]

### 3. Concrete Improvement Suggestions
- [Suggestion 1 with code reference]
- [Suggestion 2]

### 4. Confidence Score
**Confidence:** High | Medium | Low (with 1-sentence justification)
`;

  // Process prompt via agent model (or Claude CLI execution)
  const escapedPrompt = reviewPrompt.replace(/"/g, '\\"');
  const reviewMarkdown = execSync(`claude -p "${escapedPrompt}"`, { encoding: 'utf-8' });

  console.log(reviewMarkdown);
}

runReview().catch(console.error);
```

---

## 2. GitHub Actions Automation Workflow (`.github/workflows/claude-pr-review.yml`)

```yaml
name: Claude PR Reviewer
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Install Claude Code Reviewer
        run: npm install -g @anthropic-ai/claude-code

      - name: Run Review & Comment
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          REVIEW_OUTPUT=$(node bin/claude-review.js --pr "${{ github.event.pull_request.html_url }}")
          gh pr comment "${{ github.event.pull_request.number }}" --body "${REVIEW_OUTPUT}"
```
