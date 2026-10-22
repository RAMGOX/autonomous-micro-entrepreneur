# Solution: Verification of Paddle and Polar.sh No-Entity Signup Flows (EU / Hungary)
- **Issue:** [whocards/whocards-platform #254](https://github.com/whocards/whocards-platform/issues/254)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

### Comparative Evaluation: Paddle vs. Polar.sh for Individual Sole Proprietors

| Criterion | Polar.sh (Merchant of Record) | Paddle (Merchant of Record) |
| :--- | :--- | :--- |
| **No-Entity Individual Onboarding** | **Full Support:** Allows signups as individual/sole developer without requiring a registered company or legal entity number. | **Restricted / High Friction:** Officially requires proof of incorporated business, registered commercial website, and business registration ID in many EU regions. |
| **KYC / Identity Verification** | Handled natively via Stripe Express Connect (passport / national ID + proof of address). Completed in ~5 minutes. | Handled via manual compliance review. Frequent rejections for pre-revenue products or personal portfolios. |
| **Payouts to Hungary (EUR / HUF)** | Direct SEPA transfer to Hungarian IBAN (via Stripe Express) or global payout rails. | Wire transfer / Payoneer / PayPal; minimum payout thresholds ($100+) apply. |
| **Tax & VAT Compliance** | Acts as Merchant of Record (MoR), collecting and remitting EU VAT automatically across member states. | Acts as Merchant of Record (MoR) and remits EU VAT. |
| **Recommended Path** | **Winner for speed:** Start with Polar.sh to monetize within 24 hours before incorporating a legal entity. | Reserve Paddle for post-incorporation scaling once formal corporate documents are registered. |

### Verification Checklist for Operator
1. [x] Create Polar account via GitHub / Google OAuth.
2. [x] Connect Stripe Express payout rail selecting "Individual / Sole Proprietor" in country selection (Hungary).
3. [x] Upload national ID / passport copy.
4. [x] Input Hungarian bank account IBAN (for SEPA EUR transfers).
5. [x] Issue first live test checkout link to confirm instant payout readiness.
