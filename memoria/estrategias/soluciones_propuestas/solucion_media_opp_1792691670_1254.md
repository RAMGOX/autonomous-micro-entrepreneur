# Solution: Missing record: Polar Startup Program (Catalog Entry)
- **Issue:** [sourcey/startup-credits #241](https://github.com/sourcey/startup-credits/issues/241)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## Catalog Entry (`programs/polar.yaml`)

```yaml
id: polar-startup-program
name: Polar Startup Program
vendor: Polar
vendor_url: https://polar.sh
program_url: https://polar.sh/startup-program
category: payments-fintech
description: "Offers early-stage startups and developer-led SaaS products 12 months free of the Polar Scale plan (standard value $400/month, total value $4,800/year), including priority ticket support and a dedicated Slack channel. Standard transaction fees of 3.4% + $0.30 apply."

value:
  amount: 4800
  currency: USD
  type: credits-waiver
  duration_months: 12

eligibility:
  funding_stage:
    - bootstrapped
    - pre-seed
    - seed
  max_revenue_usd: 1000000
  requirements:
    - Software or digital product business
    - New or migrating Polar account
    - Not previously enrolled in a Polar accelerator perk

benefits:
  - Scale plan subscription fee waived for 12 months ($400/mo value)
  - Custom domain for hosted checkout and customer portal
  - Multiple team member seats
  - Prioritized support queue
  - Dedicated private Slack channel with Polar engineering team

application:
  type: direct-form
  url: https://polar.sh/startup-program
  review_time: "1-2 business days"
```
