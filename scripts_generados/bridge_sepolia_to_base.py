"""
Bridge: Transfiere ETH de Ethereum Sepolia (L1) a Base Sepolia (L2) usando el puente oficial OP Stack
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / "config" / ".env")

PRIV_KEY = os.getenv("PRIVATE_KEY_TESTNET")
ADDR = os.getenv("PUBLIC_ADDRESS_TESTNET") or "0x02c1F87F514493F359Afc0B3ff6b587434770361"

ETH_SEPOLIA_RPC = "https://ethereum-sepolia-rpc.publicnode.com"
L1_BRIDGE_ADDR = "0xfd0Bf71F60660E2f608ed56e1659C450eB113120"

def bridge_to_base(amount_eth: float = 0.04):
    print("=" * 60)
    print(" INICIANDO PUENTE: ETHEREUM SEPOLIA -> BASE SEPOLIA")
    print("=" * 60)
    w3 = Web3(Web3.HTTPProvider(ETH_SEPOLIA_RPC))
    
    balance_wei = w3.eth.get_balance(ADDR)
    balance_eth = float(w3.from_wei(balance_wei, "ether"))
    print(f"-> Cartera: {ADDR}")
    print(f"-> Saldo en Ethereum Sepolia: {balance_eth:.4f} ETH")
    
    if balance_eth < amount_eth:
        print(f"Saldo insuficiente para puentear {amount_eth} ETH.")
        return None
        
    abi = [{
        "inputs": [
            {"internalType": "address", "name": "_to", "type": "address"},
            {"internalType": "uint32", "name": "_minGasLimit", "type": "uint32"},
            {"internalType": "bytes", "name": "_extraData", "type": "bytes"}
        ],
        "name": "depositETHTo",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    }]
    
    contract = w3.eth.contract(address=L1_BRIDGE_ADDR, abi=abi)
    nonce = w3.eth.get_transaction_count(ADDR)
    gas_price = w3.eth.gas_price
    value_wei = w3.to_wei(amount_eth, "ether")
    
    print(f"-> Punteando {amount_eth} ETH hacia Base Sepolia...")
    tx = contract.functions.depositETHTo(ADDR, 200000, b"").build_transaction({
        "chainId": 11155111,  # Sepolia
        "from": ADDR,
        "nonce": nonce,
        "value": value_wei,
        "gasPrice": int(gas_price * 1.3),
        "gas": 800000
    })
    
    signed = w3.eth.account.sign_transaction(tx, private_key=PRIV_KEY)
    raw_tx = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    print(f"-> Transacción enviada: {tx_hash.hex()}")
    print("-> Esperando confirmación en Ethereum Sepolia...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"-> Estado: {receipt.status} (1 = Exitoso)")
    print(f"-> Confirmado en bloque {receipt.blockNumber}!")
    print(f"-> Gas usado: {receipt.gasUsed}")
    print(f"-> En ~1-2 minutos los fondos aparecerán acreditados en Base Sepolia.")
    return tx_hash.hex()

if __name__ == "__main__":
    bridge_to_base(0.04)
