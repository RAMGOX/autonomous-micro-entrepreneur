# Solution: Scope candidate: Polar (Agent-Ready Services Vendor YAML)
- **Issue:** [sourcey/agent-ready-services #182](https://github.com/sourcey/agent-ready-services/issues/182)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## Agent Readiness Service Definition (`services/payments-fintech/polar.yaml`)

```yaml
vendor: Polar
entity_id: ent_01kzc2rqsw8fpc33xb0n7tdqv5
slug: polar
category: payments-fintech
canonical_url: https://polar.sh
docs_url: https://docs.polar.sh
api_reference: https://api.polar.sh/docs

readiness_assessment:
  version: "1.0.0"
  status: ready
  tier: production

funnel:
  type: autonomous-merchant-payout
  description: "Enables autonomous AI agents and developer SaaS apps to create products, accept global credit card / crypto payments, manage customer subscriptions, and automate license key distribution with zero upfront entity requirements."
  surfaces:
    discovery:
      openapi_spec: https://api.polar.sh/openapi.json
      documentation: https://docs.polar.sh/api-reference
    authentication:
      methods:
        - Bearer Token (Personal Access Tokens / Organization Access Tokens)
      header_format: "Authorization: Bearer <POLAR_ACCESS_TOKEN>"
    provisioning:
      automated: true
      endpoint: POST /v1/products
      sdk_support:
        - "@polar-sh/sdk" (TypeScript / Node.js)
        - "polar-sdk" (Python)
    operations:
      core_endpoints:
        - GET /v1/customers
        - POST /v1/customers
        - GET /v1/subscriptions
        - GET /v1/benefit-grants
        - POST /v1/checkouts/custom
    rate_limits:
      requests_per_minute: 300
      standard_headers:
        - X-RateLimit-Limit
        - X-RateLimit-Remaining
        - X-RateLimit-Reset
    status_and_health:
      healthcheck_url: https://status.polar.sh
      uptime_sla: "99.9%"
```
