# Solution: Add Polar customer-state, subscriptions & benefit-grants data-source connector
- **Issue:** [topoteretes/cognee #5916](https://github.com/topoteretes/cognee/issues/5916)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Polar Connector Implementation (`packages/connector/polar/connector.py`)

```python
import os
from typing import AsyncGenerator, Dict, Any
from polar_sdk import Polar
from cognee.modules.data.models import DataDocument
from cognee.modules.connectors import BaseConnector

class PolarConnector(BaseConnector):
    """
    Cognee Connector for Polar.sh
    Indexes Customers, Subscriptions, and Benefit Grants into searchable Graph Knowledge Base.
    """

    def __init__(self, access_token: str = None, organization_id: str = None):
        self.access_token = access_token or os.getenv("POLAR_ACCESS_TOKEN")
        self.organization_id = organization_id or os.getenv("POLAR_ORGANIZATION_ID")
        self.client = Polar(access_token=self.access_token)

    async def fetch_data(self) -> AsyncGenerator[DataDocument, None]:
        # 1. Index Customers
        customers_page = self.client.customers.list(organization_id=self.organization_id, limit=100)
        for customer in customers_page.items:
            content = (
                f"Customer ID: {customer.id}\n"
                f"Email: {customer.email}\n"
                f"Name: {customer.name or 'N/A'}\n"
                f"Created At: {customer.created_at}\n"
            )
            yield DataDocument(
                id=f"polar_customer_{customer.id}",
                text=content,
                metadata={
                    "type": "polar_customer",
                    "email": customer.email,
                    "customer_id": customer.id
                }
            )

        # 2. Index Subscriptions
        subscriptions_page = self.client.subscriptions.list(organization_id=self.organization_id, limit=100)
        for sub in subscriptions_page.items:
            content = (
                f"Subscription ID: {sub.id}\n"
                f"Customer ID: {sub.customer_id}\n"
                f"Status: {sub.status}\n"
                f"Current Period End: {sub.current_period_end}\n"
                f"Cancel At Period End: {sub.cancel_at_period_end}\n"
            )
            yield DataDocument(
                id=f"polar_sub_{sub.id}",
                text=content,
                metadata={
                    "type": "polar_subscription",
                    "status": sub.status,
                    "customer_id": sub.customer_id
                }
            )

        # 3. Index Benefit Grants
        grants_page = self.client.benefit_grants.list(limit=100)
        for grant in grants_page.items:
            content = (
                f"Benefit Grant ID: {grant.id}\n"
                f"Benefit Type: {grant.benefit.type}\n"
                f"Customer ID: {grant.customer_id}\n"
                f"Is Granted: {grant.is_granted}\n"
            )
            yield DataDocument(
                id=f"polar_grant_{grant.id}",
                text=content,
                metadata={
                    "type": "polar_benefit_grant",
                    "customer_id": grant.customer_id,
                    "is_granted": grant.is_granted
                }
            )
```
