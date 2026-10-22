"""
Deploy Oracle: Compilador y desplegador de AgentMicroServiceOracle en Base Sepolia
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3
import solcx

BASE_DIR = Path(__file__).resolve().parent.parent
CONTRACT_PATH = BASE_DIR / "src" / "contracts" / "AgentMicroServiceOracle.sol"
BUILD_DIR = BASE_DIR / "src" / "contracts" / "build"
BUILD_DIR.mkdir(parents=True, exist_ok=True)

ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

RPC_URL = os.getenv("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org")
PRIVATE_KEY = os.getenv("PRIVATE_KEY_TESTNET")
WALLET_ADDRESS = os.getenv("PUBLIC_ADDRESS_TESTNET", "0x02c1F87F514493F359Afc0B3ff6b587434770361")

def compile_contract():
    print("-> Compilando AgentMicroServiceOracle.sol con solc 0.8.20...")
    solcx.set_solc_version("0.8.20")
    compiled = solcx.compile_files(
        [str(CONTRACT_PATH)],
        output_values=["abi", "bin"],
        solc_version="0.8.20"
    )
    
    contract_key = [k for k in compiled.keys() if "AgentMicroServiceOracle" in k][0]
    contract_interface = compiled[contract_key]
    
    output_file = BUILD_DIR / "AgentMicroServiceOracle.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(contract_interface, f, indent=2)
        
    print(f"-> Compilacion exitosa. Artefacto guardado en: {output_file}")
    return contract_interface

def deploy():
    print("=" * 60)
    print(" DESPLIEGUE DE AGENT MICRO-SERVICE ORACLE EN BASE SEPOLIA")
    print("=" * 60)
    
    artifact = compile_contract()
    abi = artifact["abi"]
    bytecode = artifact["bin"]
    
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("[Error] No hay conexion RPC con Base Sepolia.")
        return None
        
    balance_wei = w3.eth.get_balance(WALLET_ADDRESS)
    balance_eth = float(w3.from_wei(balance_wei, "ether"))
    print(f"-> Cartera: {WALLET_ADDRESS} | Saldo: {balance_eth:.6f} ETH")
    
    query_fee = w3.to_wei(0.0001, "ether")
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
    gas_price = w3.eth.gas_price
    
    tx = contract.constructor(query_fee).build_transaction({
        "chainId": 84532,
        "from": WALLET_ADDRESS,
        "nonce": nonce,
        "gasPrice": gas_price
    })
    
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    raw_tx = getattr(signed_tx, "raw_transaction", None) or getattr(signed_tx, "rawTransaction", None)
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    print(f"-> Transaccion enviada: {tx_hash.hex()}")
    print("-> Esperando confirmacion en bloque...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    
    deployed_address = receipt.contractAddress
    print(f"-> Contrato desplegado con exito!")
    print(f"-> Direccion del Contrato: {deployed_address}")
    print(f"-> Explorador: https://sepolia.basescan.org/address/{deployed_address}")
    
    # Guardar en memoria de Obsidian
    contratos_file = BASE_DIR / "memoria" / "estrategias" / "contratos_desplegados.md"
    entry = f"""
### AgentMicroServiceOracle (Oraculo y Monetizacion de Micro-Servicios)
- **Direccion:** `{deployed_address}`
- **Red:** Base Sepolia Testnet (Chain ID 84532)
- **Desplegado por:** `{WALLET_ADDRESS}`
- **Tx Hash:** `{tx_hash.hex()}`
- **Cuota de consulta inicial:** `0.0001 ETH`
- **Capacidades:** Heartbeats criptograficos, atestacion de scraping y cobro de recompensas.
"""
    with open(contratos_file, "a", encoding="utf-8") as f:
        f.write(entry)
        
    return deployed_address

if __name__ == "__main__":
    deploy()
