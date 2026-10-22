"""
Continuous Autonomous Worker: Motor continuo de investigación y ejecución 24/7
Rastrea oportunidades, registra micro-tareas on-chain en Base Sepolia, emite heartbeats al Oráculo,
cobra automáticamente los beneficios generados y actualiza Obsidian.
"""
import os
import sys
import time
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))
sys.path.append(str(BASE_DIR / "scripts_generados"))

ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from opportunity_scraper import scrape_and_analyze
from discord_bridge import notify_user_discord

PRIV_KEY = os.getenv("PRIVATE_KEY_TESTNET")
ADDR = os.getenv("PUBLIC_ADDRESS_TESTNET", "0x02c1F87F514493F359Afc0B3ff6b587434770361")
RPC_URL = os.getenv("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org")
CONTRACT_ADDR = "0x04f473e39e678d012F1f42cba7649F248253cb56"
ORACLE_CONTRACT_ADDR = "0x75145e53B139B86062cdE5098761a28D76578fD4"
STATE_FILE = BASE_DIR / "memoria" / "estado" / "worker_state.json"

TARGET_SOURCES = [
    ("https://docs.base.org/docs/chain/network-information", "Infraestructura Base Sepolia"),
    ("https://raw.githubusercontent.com/ethereum-optimism/ecosystem/main/README.md", "Ecosistema Optimism y Base"),
    ("https://raw.githubusercontent.com/coinbase/agentkit/main/README.md", "Coinbase AgentKit Onchain AI"),
    ("https://raw.githubusercontent.com/coinbase/agentkit/main/python/README.md", "AgentKit Python SDK Base Sepolia"),
    ("https://raw.githubusercontent.com/ethereum-optimism/superchain-registry/main/README.md", "Superchain Registry e Interoperabilidad Base"),
    ("https://raw.githubusercontent.com/OpenZeppelin/openzeppelin-contracts/master/README.md", "OpenZeppelin Contratos Estándar en Base"),
    ("https://raw.githubusercontent.com/ethereum/ERCs/master/ERCS/erc-4337.md", "ERC-4337 Account Abstraction y Paymasters"),
    ("https://raw.githubusercontent.com/smartcontractkit/chainlink/develop/README.md", "Chainlink Automation y Keepers para Agentes"),
    ("https://raw.githubusercontent.com/pyth-network/pyth-crosschain/main/README.md", "Pyth Network Oráculos de Precios en Base"),
    ("https://raw.githubusercontent.com/Uniswap/v3-periphery/main/README.md", "Uniswap v3 Swaps y Liquidez en Base"),
    ("https://raw.githubusercontent.com/safe-global/safe-smart-account/main/README.md", "Safe Smart Accounts y Multi-Firma en Base"),
    ("https://raw.githubusercontent.com/graphprotocol/graph-node/master/README.md", "The Graph Indexación de Datos en Base Sepolia")
]

def load_worker_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"current_index": 2, "total_runs": 2}

def save_worker_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def record_task_onchain(title: str, metadata_uri: str):
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        artifact_path = BASE_DIR / "src" / "contracts" / "build" / "MicroTaskRegistry.json"
        if not artifact_path.exists():
            return None
        with open(artifact_path, "r", encoding="utf-8") as f:
            artifact = json.load(f)
            
        contract = w3.eth.contract(address=CONTRACT_ADDR, abi=artifact["abi"])
        nonce = w3.eth.get_transaction_count(ADDR)
        gas_price = w3.eth.gas_price
        
        tx = contract.functions.recordTask(title, metadata_uri).build_transaction({
            "chainId": 84532,
            "from": ADDR,
            "nonce": nonce,
            "gasPrice": gas_price
        })
        signed = w3.eth.account.sign_transaction(tx, private_key=PRIV_KEY)
        raw_tx = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)
        tx_hash = w3.eth.send_raw_transaction(raw_tx)
        print(f"-> Micro-tarea registrada on-chain: {tx_hash.hex()}")
        return tx_hash.hex()
    except Exception as e:
        print(f"[OnChain Error] No se pudo registrar la tarea: {e}")
        return None

def post_heartbeat_onchain():
    """Emite un Heartbeat con hash de estado criptográfico al contrato AgentMicroServiceOracle"""
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        artifact_path = BASE_DIR / "src" / "contracts" / "build" / "AgentMicroServiceOracle.json"
        if not artifact_path.exists():
            return None
        with open(artifact_path, "r", encoding="utf-8") as f:
            artifact = json.load(f)
            
        state_digest = Web3.keccak(text=f"heartbeat_{time.time()}_{ADDR}")
        contract = w3.eth.contract(address=ORACLE_CONTRACT_ADDR, abi=artifact["abi"])
        nonce = w3.eth.get_transaction_count(ADDR)
        gas_price = w3.eth.gas_price
        
        tx = contract.functions.postHeartbeat(state_digest).build_transaction({
            "chainId": 84532,
            "from": ADDR,
            "nonce": nonce,
            "gasPrice": gas_price
        })
        signed = w3.eth.account.sign_transaction(tx, private_key=PRIV_KEY)
        raw_tx = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)
        tx_hash = w3.eth.send_raw_transaction(raw_tx)
        print(f"-> Heartbeat emitido al Oráculo: {tx_hash.hex()}")
        return tx_hash.hex()
    except Exception as e:
        print(f"[Oracle Heartbeat Warning]: {e}")
        return None

def claim_all_earnings():
    """Retira automáticamente cualquier saldo o ganancia acumulada en contratos hacia la cartera del operador"""
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        artifact_path = BASE_DIR / "src" / "contracts" / "build" / "AgentMicroServiceOracle.json"
        if not artifact_path.exists():
            return None
            
        contract_bal = w3.eth.get_balance(ORACLE_CONTRACT_ADDR)
        if contract_bal > 0:
            print(f"-> [Auto-Claim] Beneficios detectados en Oráculo: {w3.from_wei(contract_bal, 'ether')} ETH. Retirando...")
            with open(artifact_path, "r", encoding="utf-8") as f:
                artifact = json.load(f)
            contract = w3.eth.contract(address=ORACLE_CONTRACT_ADDR, abi=artifact["abi"])
            nonce = w3.eth.get_transaction_count(ADDR)
            gas_price = w3.eth.gas_price
            
            tx = contract.functions.withdrawEarnings().build_transaction({
                "chainId": 84532,
                "from": ADDR,
                "nonce": nonce,
                "gasPrice": gas_price
            })
            signed = w3.eth.account.sign_transaction(tx, private_key=PRIV_KEY)
            raw_tx = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)
            tx_hash = w3.eth.send_raw_transaction(raw_tx)
            print(f"-> [Auto-Claim Exitoso] Fondos transferidos a cartera {ADDR}: {tx_hash.hex()}")
            
            notify_user_discord(
                f"Retirados {w3.from_wei(contract_bal, 'ether')} ETH a tu cartera `{ADDR}`.\nTx: `{tx_hash.hex()}`",
                title="💰 Cobro Automático de Beneficios Ejecutado",
                color=0x2ecc71
            )
            return tx_hash.hex()
    except Exception as e:
        print(f"[Auto-Claim Warning] {e}")
        return None

async def run_continuous_cycle():
    print("=" * 60)
    print(" INICIANDO CICLO DEL MOTOR AUTÓNOMO CONTINUO 24/7")
    print(f" Hora de ejecución: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. Comprobar Cartera Web3
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    balance_eth = float(w3.from_wei(w3.eth.get_balance(ADDR), "ether"))
    print(f"-> Cartera: {ADDR} | Saldo: {balance_eth:.4f} ETH")

    # 2. Selección rotativa del objetivo de minería
    state = load_worker_state()
    curr_idx = state.get("current_index", 0) % len(TARGET_SOURCES)
    url, theme = TARGET_SOURCES[curr_idx]

    try:
        print(f"-> Minando objetivo #{curr_idx + 1}: {theme} ({url})...")
        res = await scrape_and_analyze(url, theme)
        if res:
            # Registrar tarea en blockchain
            tx = record_task_onchain(f"Análisis Web3: {theme}", f"obsidian://memoria/estrategias/oportunidades_detectadas.md")
            if tx:
                print(f"-> Micro-tarea #{state.get('total_runs', 2) + 1} registrada silenciosamente en blockchain.")
                
            # Emitir Heartbeat de SLA al Oráculo cada 3 tareas
            if state.get("total_runs", 0) % 3 == 0:
                post_heartbeat_onchain()
                
            # Cobrar automáticamente cualquier beneficio generado
            claim_all_earnings()
    except Exception as e:
        print(f"[Aviso Scraper] {e}")

    # Avanzar índice
    state["current_index"] = (curr_idx + 1) % len(TARGET_SOURCES)
    state["total_runs"] = state.get("total_runs", 2) + 1
    state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_worker_state(state)

    print("=" * 60)
    print(" CICLO COMPLETADO CON ÉXITO.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_continuous_cycle())
