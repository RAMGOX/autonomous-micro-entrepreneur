# Solution: [BOUNTY $200] WORKFLOW: n8n + Claude Code — automated weekly dev summary
- **Issue:** [claude-builders-bounty/claude-builders-bounty #5](https://github.com/claude-builders-bounty/claude-builders-bounty/issues/5)
- **Bounty:** $200 USD (powered by Opire)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Exportable n8n Workflow (`workflows/weekly-github-claude-summary.json`)

```json
{
  "name": "Weekly GitHub Dev Summary with Claude",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "weeks",
              "triggerAtHour": 17,
              "triggerAtDay": 5
            }
          ]
        }
      },
      "id": "1",
      "name": "Schedule Trigger (Friday 5PM)",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [250, 300]
    },
    {
      "parameters": {
        "url": "=https://api.github.com/repos/{{$env.GITHUB_REPOSITORY}}/commits?since={{new Date(Date.now() - 7*24*60*60*1000).toISOString()}}",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "options": {}
      },
      "id": "2",
      "name": "Fetch Commits (Last 7 Days)",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [480, 200]
    },
    {
      "parameters": {
        "url": "=https://api.github.com/repos/{{$env.GITHUB_REPOSITORY}}/pulls?state=closed&sort=updated&direction=desc",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "options": {}
      },
      "id": "3",
      "name": "Fetch Merged PRs",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [480, 400]
    },
    {
      "parameters": {
        "model": "claude-sonnet-4-20250514",
        "prompt": "=Generate a comprehensive narrative executive summary of this week's engineering progress for repo {{$env.GITHUB_REPOSITORY}}.\n\nCommits:\n{{JSON.stringify($('Fetch Commits (Last 7 Days)').all().map(c => c.json.commit.message))}}\n\nMerged Pull Requests:\n{{JSON.stringify($('Fetch Merged PRs').all().filter(p => p.json.merged_at).map(p => ({title: p.json.title, user: p.json.user.login})))}}",
        "system": "You are a Chief Technology Officer. Structure the report with: 1. Key Achievements, 2. Architecture & Code Changes, 3. Contributors Highlight, 4. Next Week Focus."
      },
      "id": "4",
      "name": "Claude AI Synthesis",
      "type": "@n8n/n8n-nodes-langchain.chainLlm",
      "typeVersion": 1.4,
      "position": [780, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "={{$env.DISCORD_WEBHOOK_URL}}",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "content",
              "value": "=🚀 **Weekly Engineering Digest for {{$env.GITHUB_REPOSITORY}}**\n\n{{$('Claude AI Synthesis').item.json.text}}"
            }
          ]
        }
      },
      "id": "5",
      "name": "Deliver Discord Notification",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1050, 300]
    }
  ],
  "connections": {
    "Schedule Trigger (Friday 5PM)": {
      "main": [
        [
          { "node": "Fetch Commits (Last 7 Days)", "type": "main", "index": 0 },
          { "node": "Fetch Merged PRs", "type": "main", "index": 0 }
        ]
      ]
    },
    "Fetch Commits (Last 7 Days)": {
      "main": [
        [{ "node": "Claude AI Synthesis", "type": "main", "index": 0 }]
      ]
    },
    "Fetch Merged PRs)": {
      "main": [
        [{ "node": "Claude AI Synthesis", "type": "main", "index": 0 }]
      ]
    },
    "Claude AI Synthesis": {
      "main": [
        [{ "node": "Deliver Discord Notification", "type": "main", "index": 0 }]
      ]
    }
  }
}
```
