"""
Web3 Wallet Manager: Consulta de balance, gas y estado de Base Sepolia Testnet
Inspirado en el WalletProvider de Coinbase AgentKit
"""
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

RPC_URL = os.getenv("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org")
WALLET_ADDRESS = os.getenv("PUBLIC_ADDRESS_TESTNET", "0x02c1F87F514493F359Afc0B3ff6b587434770361")
PRIVATE_KEY = os.getenv("PRIVATE_KEY_TESTNET")

def check_wallet_status():
    print("=" * 60)
    print(" GESTOR DE CARTERA WEB3 - BASE SEPOLIA TESTNET")
    print("=" * 60)
    
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    is_connected = w3.is_connected()
    print(f"-> Conectado a Base Sepolia ({RPC_URL}): {is_connected}")
    
    if not is_connected:
        print("[Error] No se pudo conectar al nodo RPC de Base Sepolia.")
        return None
        
    latest_block = w3.eth.block_number
    gas_price_gwei = w3.from_wei(w3.eth.gas_price, "gwei")
    
    balance_wei = w3.eth.get_balance(WALLET_ADDRESS)
    balance_eth = float(w3.from_wei(balance_wei, "ether"))
    
    print(f"-> Dirección de Cartera: {WALLET_ADDRESS}")
    print(f"-> Bloque más reciente: #{latest_block}")
    print(f"-> Precio de Gas actual: {gas_price_gwei:.2f} Gwei")
    print(f"-> Balance de ETH Testnet: {balance_eth:.6f} ETH")
    
    # Actualizar estado en Obsidian
    memoria_file = BASE_DIR / "memoria" / "estado" / "cartera_web3.md"
    content = f"""# Cartera Web3 Oficial (Base Sepolia Testnet)

- **Red:** Base Sepolia (Ethereum Layer 2 Testnet)
- **Chain ID:** `84532`
- **RPC:** `{RPC_URL}`
- **Explorador:** [Ver en Basescan](https://sepolia.basescan.org/address/{WALLET_ADDRESS})
- **Dirección Pública:** `{WALLET_ADDRESS}`
- **Último bloque verificado:** `#{latest_block}`
- **Balance actual:** `{balance_eth:.6f} ETH`
- **Última sincronización:** `{time.strftime("%Y-%m-%d %H:%M:%S")}`
- **Estado de Gas:** `Normal ({gas_price_gwei:.2f} Gwei)`
- **Regla de Seguridad:** Exclusiva para Testnet. Fondos ficticios sin riesgo financiero.

## Faucets Oficiales para Recargar Fondos de Prueba
1. **Coinbase CDP Faucet:** Permite recargar 0.05 ETH directamente a la dirección.
2. **Chainlink Faucet:** `https://faucets.chain.link/base-sepolia`
3. **Alchemy Base Sepolia:** `https://www.alchemy.com/faucets/base-sepolia`
"""
    with open(memoria_file, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("-> Ficha en Obsidian actualizada: memoria/estado/cartera_web3.md")
    print("=" * 60)
    
    return {
        "address": WALLET_ADDRESS,
        "balance_eth": balance_eth,
        "latest_block": latest_block,
        "gas_price_gwei": float(gas_price_gwei)
    }

if __name__ == "__main__":
    check_wallet_status()
