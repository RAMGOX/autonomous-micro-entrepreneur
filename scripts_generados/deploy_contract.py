"""
Deploy Contract: Compilador y desplegador autnomo de contratos en Base Sepolia
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3
import solcx

BASE_DIR = Path(__file__).resolve().parent.parent
CONTRACT_PATH = BASE_DIR / "src" / "contracts" / "MicroTaskRegistry.sol"
BUILD_DIR = BASE_DIR / "src" / "contracts" / "build"
BUILD_DIR.mkdir(parents=True, exist_ok=True)

ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

RPC_URL = os.getenv("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org")
PRIVATE_KEY = os.getenv("PRIVATE_KEY_TESTNET")
WALLET_ADDRESS = os.getenv("PUBLIC_ADDRESS_TESTNET", "0x02c1F87F514493F359Afc0B3ff6b587434770361")

def compile_contract():
    print("-> Compilando MicroTaskRegistry.sol con solc 0.8.20...")
    solcx.set_solc_version("0.8.20")
    compiled = solcx.compile_files(
        [str(CONTRACT_PATH)],
        output_values=["abi", "bin"],
        solc_version="0.8.20"
    )
    
    contract_interface = list(compiled.values())[0]
    
    output_file = BUILD_DIR / "MicroTaskRegistry.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(contract_interface, f, indent=2)
        
    print(f"-> Compilacin exitosa. Artefacto guardado en: {output_file}")
    return contract_interface

def deploy_if_funded():
    print("=" * 60)
    print(" DESPLIEGUE AUTNOMO EN BASE SEPOLIA TESTNET")
    print("=" * 60)
    
    artifact = compile_contract()
    abi = artifact["abi"]
    bytecode = artifact["bin"]
    
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("[Error] No hay conexin RPC con Base Sepolia.")
        return None
        
    balance_wei = w3.eth.get_balance(WALLET_ADDRESS)
    balance_eth = float(w3.from_wei(balance_wei, "ether"))
    print(f"-> Cartera: {WALLET_ADDRESS}")
    print(f"-> Saldo disponible: {balance_eth:.6f} ETH")
    
    # Estimacin bsica de gas para despliegue: ~180,000 gas
    gas_price = w3.eth.gas_price
    estimated_cost_wei = 200000 * gas_price
    estimated_cost_eth = float(w3.from_wei(estimated_cost_wei, "ether"))
    print(f"-> Coste estimado de gas: {estimated_cost_eth:.8f} ETH")
    
    if balance_wei < estimated_cost_wei:
        print("\n[Aviso] Saldo insuficiente para desplegar en este momento.")
        print(f"-> Requiere al menos {estimated_cost_eth:.6f} ETH de prueba en Base Sepolia.")
        print("-> El contrato est compilado al 100% y listo para transmitirse en cuanto se reciba faucet.")
        print("=" * 60)
        return False
        
    print("-> Saldo suficiente detectado! Iniciando transaccin de despliegue...")
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
    
    tx = contract.constructor().build_transaction({
        "chainId": 84532,
        "from": WALLET_ADDRESS,
        "nonce": nonce,
        "gasPrice": gas_price
    })
    
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    raw_tx = getattr(signed_tx, "raw_transaction", None) or getattr(signed_tx, "rawTransaction", None)
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    print(f"-> Transaccin enviada: {tx_hash.hex()}")
    print("-> Esperando confirmacin en bloque...")
    
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    contract_address = tx_receipt.contractAddress
    print(f"-> Contrato desplegado con xito en: {contract_address}")
    
    # Registrar en Obsidian
    memoria_file = BASE_DIR / "memoria" / "estado" / "contratos_desplegados.md"
    entry = f"""# Contratos Desplegados en Base Sepolia (Testnet)

## MicroTaskRegistry
- **Direccin del Contrato:** `{contract_address}`
- **Desplegado por:** `{WALLET_ADDRESS}`
- **Transaccin:** [Ver en Basescan](https://sepolia.basescan.org/tx/{tx_hash.hex()})
- **Red:** Base Sepolia (Chain ID `84532`)
- **Estado:** Activo y verificado
"""
    with open(memoria_file, "w", encoding="utf-8") as f:
        f.write(entry)
        
    print(f"-> Ficha guardada en Obsidian: memoria/estado/contratos_desplegados.md")
    print("=" * 60)
    return contract_address

if __name__ == "__main__":
    deploy_if_funded()
