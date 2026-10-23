from pathlib import Path

p = Path(r"C:\Users\Antonio Ramos\autonomous-micro-entrepreneur\README.md")
text = p.read_text(encoding="utf-8")

target = "Built specifically for the **Base (Coinbase L2)** ecosystem, it settles cryptographic proofs of work on-chain via smart contracts and operates unattended on dedicated hardware (NVIDIA GeForce GTX 1660 / Windows 10)."

section = """

---

## 🌐 Public x402 Micropayment API & Agent Services (Base L2)

AME exposes a pay-per-request API following the **HTTP 402 (x402) Payment Required** standard on **Base Mainnet (ChainId: 8453)**. External AI agents, developers, and autonomous protocols can hire AME for on-demand intelligence and code resolution with instant on-chain settlement:

* **Live Dashboard & Explorer:** [https://ramgox.github.io/autonomous-micro-entrepreneur/](https://ramgox.github.io/autonomous-micro-entrepreneur/)
* **AIP-1 Agent Manifest:** [`/.well-known/agent.json`](docs/api_gateway.json)
* **OpenAPI 3.0 Specification:** [`/openapi.json`](docs/api_gateway.json)
* **Payee Address (Base L2):** [`0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf`](https://basescan.org/address/0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf)

### Service Catalog & Micro-Pricing

| Endpoint | Method | Cost | Description |
| :--- | :---: | :---: | :--- |
| `/api/v1/x402/pricing` | `GET` | **Free** | Public pricing schedule & payment challenge specifications |
| `/api/v1/x402/intel` | `GET` | `0.00005 ETH` (~$0.13) | Curated multi-chain transaction analytics & on-chain intelligence |
| `/api/v1/x402/solve` | `POST` | `0.0001 ETH` (~$0.26) | Autonomous code resolution, smart contract audits & bug solving |

### How to Call AME via cURL

```bash
# 1. Fetch live pricing and payee address
curl -s https://enforcement-valid-carrying-slip.trycloudflare.com/api/v1/x402/pricing

# 2. Query intelligence (pass transaction hash confirming 0.00005 ETH sent on Base)
curl -s -H "X-Payment-Tx: <0x_BASE_TX_HASH>" \\
     https://enforcement-valid-carrying-slip.trycloudflare.com/api/v1/x402/intel
```"""

if target in text:
    new_text = text.replace(target, target + section, 1)
    p.write_text(new_text, encoding="utf-8")
    print("README.md updated successfully")
else:
    print("Target string not found in README.md")
