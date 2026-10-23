# 🚀 Autonomous Micro-Entrepreneur (AME)
### Autonomous 24/7 AI Agent Platform for On-Chain Micro-Services, Intelligence Curation & Bounties on Base L2

[![Network](https://img.shields.io/badge/Network-Base%20L2%20(EVM)-0052FF?style=flat&logo=coinbase)](https://base.org)
[![Smart Contract](https://img.shields.io/badge/Contract-BaseScan%20Verified-34D399?style=flat&logo=ethereum)](https://sepolia.basescan.org/address/0x04f473e39e678d012F1f42cba7649F248253cb56)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python)](https://python.org)
[![Runtime](https://img.shields.io/badge/Inference-Local%20GPU%20+%20Cloud%20Hybrid-7C3AED)](https://github.com/ollama/ollama)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Autonomous Micro-Entrepreneur (AME)** is a self-hosted, 24/7 agentic software system designed to perform automated micro-tasks, Web3 data curation, and code solutions with near-zero marginal operating cost. 

Built specifically for the **Base (Coinbase L2)** ecosystem, it settles cryptographic proofs of work on-chain via smart contracts and operates unattended on dedicated hardware (NVIDIA GeForce GTX 1660 / Windows 10).

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
curl -s -H "X-Payment-Tx: <0x_BASE_TX_HASH>" \
     https://enforcement-valid-carrying-slip.trycloudflare.com/api/v1/x402/intel
```

---

## 🏛️ The 4-Brain Hybrid Orchestration Architecture

AME employs an enrouted multi-model hierarchy designed to maximize reasoning power while enforcing strict token budget limits:

```
                          ┌───────────────────────────┐
                          │   Brain Router / Router   │
                          └─────────────┬─────────────┘
                                        │
        ┌───────────────────┬───────────┴───────────┬───────────────────┐
        ▼                   ▼                       ▼                   ▼
┌───────────────┐   ┌───────────────┐       ┌───────────────┐   ┌───────────────┐
│    Brain 1    │   │    Brain 2    │       │    Brain 3    │   │    Brain 4    │
│  Local Worker │   │  Ops Director │       │  Software CTO │   │  Gov Auditor  │
│(Qwen 2.5 Coder│   │(Gemini Flash) │       │(DeepSeek API) │   │ (Argon / AGY) │
│   GTX 1660)   │   │  $0.00 Cost   │       │ €0.50/day Cap │   │ High Priority │
└───────┬───────┘   └───────┬───────┘       └───────┬───────┘   └───────┬───────┘
        │                   │                       │                   │
  Headless Crawl      Macro Planning          Code Solutions       Governance &
  & Scraping 24/7     & Discord Chat          & Smart Contracts    Batch Fallback
```

1. **Brain 1: The Local Worker ($0.00 Cost)**
   * **Engine:** Ollama running `qwen2.5-coder:7b-instruct-q4_K_S` accelerated by CUDA on local Nvidia GTX 1660 (6 GB VRAM).
   * **Responsibilities:** Continuous background monitoring, Discord socket handling, headless web scraping via Crawl4AI, and Obsidian local memory synchronization.

2. **Brain 2: The Operations Director ($0.00 Incremental)**
   * **Engine:** Google Gemini Flash via Google AI Studio / Antigravity Pro.
   * **Responsibilities:** Macro task decomposition, real-time natural language synthesis, and fast conversational intelligence.

3. **Brain 3: The Software Engineer / CTO (€0.50/day Hard Cap)**
   * **Engine:** DeepSeek API managed by LiteLLM with automatic circuit breaker.
   * **Responsibilities:** Generating production-ready code solutions, EVM smart contracts, automated unit testing, and GitHub Pull Request formatting.

4. **Brain 4: The Supreme Architect & Auditor**
   * **Engine:** Argon / Antigravity Pro.
   * **Responsibilities:** High-impact technical verification (difficulty ≥ 8/10), financial safety guardrails, and automated batch fallback to process top pending opportunities when high-level tasks are clear.

---

## ⛓️ Verified On-Chain Footprint on Base

The system operates autonomously with verifiable transactions on Base:

* **Primary Smart Contract:** [`MicroTaskRegistry.sol`](https://sepolia.basescan.org/address/0x04f473e39e678d012F1f42cba7649F248253cb56)
  * **Network:** Base Sepolia (L2 Testnet) $\rightarrow$ Ready for Base Mainnet.
  * **Verified Contract Address:** `0x04f473e39e678d012F1f42cba7649F248253cb56`
  * **On-Chain Commitments:** 23+ verifiable autonomous micro-tasks registered and anchored into the blockchain.
* **Oracle & Yield Infrastructure:**
  * [`PreciousMetalsOracleAdapter.sol`](src/contracts/AgentMicroServiceOracle.sol): Dual Pyth/Chainlink oracle adapter deployed on Base.
  * Yield and staking helper patches with 100% unit test coverage.
* **Operator Payout Wallet:** `0x02c1F87F514493F359Afc0B3ff6b587434770361` (EVM compatible on Base Mainnet, Ethereum, Arbitrum, and Polygon).

---

## 🛠️ Core Autonomous Engines

### 1. Concurrent 24/7 Autonomous Daemon (`scripts_generados/autonomous_daemon.py`)
Decoupled multi-threaded pipeline running 5 independent asynchronous workers:
* **Orders Worker (5s):** Instant execution of user directives from Discord.
* **DeepSeek Solver (300s):** Strict 5-minute automated code execution targeting medium and low complexity tasks.
* **Escrow Bounty Hunter (180s):** Multi-query GitHub scanner filtering for verified on-chain escrow deposits.
* **Web3 On-Chain Pipeline (30s):** Automated state validation, heartbeat emission, and contract task registration.
* **Grants Curator (1800s):** Continuous intelligence mining of developer grant opportunities.

### 2. Escrow-Shielded Opportunity Queue (`src/opportunity_queue.py`)
* **Spam & Donation Filter:** Automatically discards donation solicitations and unbacked tokens.
* **Escrow Priority Sorting:** Prioritizes opportunities backed by on-chain escrow platforms (**Algora**, **Polar.sh**, **poidh.xyz**, **Gitcoin**).
* **TTL Auto-Pruning:** Removes tasks unexecuted after 2 hours (7,200s) to keep memory lean.
* **Cerebro 4 Batch Fallback:** Ensures high-tier models never sit idle when high-level queues are empty.

### 3. Web3 Grants & Intelligence Curator (`src/data_curator.py`)
* Leverages local `Crawl4AI` in headless mode (zero marginal cost) to scrape and structure funding opportunities across Base Ecosystem, Coinbase Developer Platform (CDP), and L2 hackathons into structured JSON and Markdown datasets.

### 4. Live Telemetry Web Dashboard (`src/dashboard_server.py`)
* Lightweight HTTP service running on `http://127.0.0.1:8080`.
* Real-time metrics: GPU temperature, VRAM allocation, CPU/RAM usage, gas price history, Web3 balance, and DeepSeek daily budget progress.

### 5. Discord Remote Command & Control (`src/discord_bot.py`)
* **Dual-Engine Visual Capture:** Attempts native desktop capture; if screen is locked or in power-save mode, automatically launches headless Chromium via Crawl4AI to snapshot the live web dashboard.
* **Zero-Noise Policy:** Routine task discovery and deliveries are logged silently to disk. Discord only triggers for user replies, system improvements, incoming real payments, urgent human intervention, and scheduled 12-hour reports (09:00 / 21:00).
* **Single-Instance Mutex Protection:** Native Windows kernel mutex (`Global\AutonomousMicroEntrepreneur_SingleInstance`) prevents duplicate bot processes.

---

## 📁 Repository Structure

```
autonomous-micro-entrepreneur/
├── config/
│   ├── .env.example              # Public configuration template
│   └── .env                      # Local keys & credentials (Git-ignored)
├── memoria/                      # Long-term persistent memory (Obsidian vault)
│   ├── datasets_curados/         # Structured Web3 grants & intelligence datasets
│   ├── estrategias/              # Revenue strategies & grant application dossiers
│   │   ├── dossier_base_builder_grant.md
│   │   └── soluciones_propuestas/# Generated code solutions & test suites
│   ├── estado/                   # Telemetry states, budgets, and opportunity queues
│   └── lecciones/                # Post-mortem logs and learned constraints
├── scripts_generados/            # Core autonomous background workers
│   ├── autonomous_daemon.py      # Main decoupled 24/7 concurrent daemon
│   ├── continuous_worker.py      # On-chain Base Sepolia interaction loop
│   └── opportunity_scraper.py    # Headless Crawl4AI mining pipeline
├── src/                          # Modular source code
│   ├── bounty_hunter.py          # Escrow-shielded GitHub & Web3 task scanner
│   ├── brain_router.py           # 4-Brain intelligent LLM router & budget manager
│   ├── dashboard_server.py       # Live telemetry server (Port 8080)
│   ├── data_curator.py           # Base Ecosystem grants extractor
│   ├── deepseek_solver.py        # Automated code generator with budget guard
│   ├── discord_bot.py            # Remote command & control bridge
│   ├── github_deliverer.py       # Automated Pull Request & comment submission
│   ├── opportunity_queue.py      # Queue manager with escrow verification & TTL
│   ├── system_watchdog.py        # Sub-2s process supervisor & auto-recovery
│   ├── twelve_hour_reporter.py   # Scheduled 09:00 / 21:00 executive reports
│   └── contracts/                # Solidity contracts (MicroTaskRegistry, Oracle)
├── Arrancar_Bot.bat              # One-click Windows launch script
├── SYSTEM_PROMPT.md              # Central operating constitution
└── README.md                     # Project documentation
```

---

## ⚡ Quickstart

### Prerequisites
* Windows 10/11 or Linux with Python 3.11+
* Local Ollama instance with `qwen2.5-coder:7b-instruct-q4_K_S`
* Dedicated or integrated GPU (CUDA supported)

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/RAMGOX/autonomous-micro-entrepreneur.git
   cd autonomous-micro-entrepreneur
   ```

2. Create virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # On Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp config/.env.example config/.env
   # Edit config/.env with your API keys and Base wallet details
   ```

4. Launch the system:
   ```bash
   # Starts Watchdog, Dashboard, Discord Bot, and 24/7 Daemon
   python src/system_watchdog.py
   ```

---

## 📜 Grant Application & Ecosystem Alignment

This project is submitted for consideration under the **Base Builder Grants (Retroactive Funding)** and **Coinbase Developer Platform (CDP) for Agents** initiatives. 

Review the complete grant dossier in [`memoria/estrategias/dossier_base_builder_grant.md`](memoria/estrategias/dossier_base_builder_grant.md).

* **Operator / Recipient Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`
* **Maintainer:** [RAMGOX](https://github.com/RAMGOX)
* **License:** MIT
