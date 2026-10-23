"""
x402 Gateway: Servidor de Micro-pagos HTTP 402 para Agentes de IA en Base L2.
Permite monetizar el sistema autonomo como un Agente-as-a-Service on-chain.
Los clientes o agentes externos reciben un codigo HTTP 402 (Payment Required)
y al liquidar una micro-transaccion en Base (0.0001 ETH), sus fondos van
directamente a la cartera Coinbase del usuario (0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf).
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, Tuple
from web3 import Web3

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from discord_bridge import notify_user_discord

BASE_MAINNET_RPC = "https://mainnet.base.org"
USER_PAYOUT_WALLET = os.getenv("USER_PAYOUT_WALLET", "0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf")
PROCESSED_TXS_FILE = BASE_DIR / "memoria" / "estado" / "x402_processed_txs.json"

PRICING_TABLE = {
    "solve": {
        "description": "Resolucion de codigo, analisis o auditoria tecnica via Cerebro Central (IA)",
        "amount_eth": 0.0001,
        "amount_wei": 100000000000000,
        "amount_usd_est": 0.26
    },
    "intel": {
        "description": "Acceso a la base de datos curada de bounties y oportunidades en Base",
        "amount_eth": 0.00005,
        "amount_wei": 50000000000000,
        "amount_usd_est": 0.13
    }
}

class X402Gateway:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(BASE_MAINNET_RPC, request_kwargs={"timeout": 6}))
        self.payout_address = Web3.to_checksum_address(USER_PAYOUT_WALLET)
        self.processed_txs = self._load_processed_txs()

    def _load_processed_txs(self) -> set:
        if PROCESSED_TXS_FILE.exists():
            try:
                with open(PROCESSED_TXS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data.keys())
            except Exception:
                pass
        return set()

    def _save_processed_tx(self, tx_hash: str, payer: str, value_eth: float, service: str):
        self.processed_txs.add(tx_hash.lower())
        data = {}
        if PROCESSED_TXS_FILE.exists():
            try:
                with open(PROCESSED_TXS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[tx_hash.lower()] = {
            "payer": payer,
            "value_eth": value_eth,
            "service": service,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        PROCESSED_TXS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PROCESSED_TXS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_payment_challenge(self, service: str = "solve") -> Dict[str, Any]:
        cfg = PRICING_TABLE.get(service, PRICING_TABLE["solve"])
        return {
            "error": "Payment Required",
            "status": 402,
            "x402": {
                "version": "1.0",
                "protocol": "x402",
                "network": "base",
                "chainId": 8453,
                "scheme": "exact",
                "payee": self.payout_address,
                "asset": "ETH",
                "amount": str(cfg["amount_eth"]),
                "amountWei": str(cfg["amount_wei"]),
                "amountUsdEst": cfg["amount_usd_est"],
                "service": service,
                "description": cfg["description"],
                "headerRequired": "X-Payment-Tx",
                "instructions": (
                    f"Send {cfg['amount_eth']} ETH on Base Mainnet to {self.payout_address}. "
                    "Then retry this request with header 'X-Payment-Tx: <tx_hash>'."
                )
            }
        }

    def verify_payment_tx(self, tx_hash: str, service: str = "solve") -> Tuple[bool, str, Dict[str, Any]]:
        tx_hash_clean = tx_hash.strip().lower()
        if not tx_hash_clean.startswith("0x") or len(tx_hash_clean) != 66:
            return False, "Formato de tx_hash invalido (debe ser 0x seguido de 64 caracteres hex).", {}

        # Anti-replay attack check
        if tx_hash_clean in self.processed_txs:
            return False, "Transaccion ya consumida previamente (anti-replay). Envie una nueva transaccion.", {}

        try:
            rcpt = self.w3.eth.get_transaction_receipt(tx_hash_clean)
            if not rcpt:
                return False, "Transaccion aun no minada o no encontrada en Base Mainnet.", {}
            if rcpt.status != 1:
                return False, "La transaccion fallo on-chain en Base.", {}

            tx = self.w3.eth.get_transaction(tx_hash_clean)
            if not tx:
                return False, "Detalles de la transaccion no disponibles.", {}

            to_addr = (tx.to or "").lower()
            if to_addr != self.payout_address.lower():
                return False, f"El destinatario no coincide. Se esperaba {self.payout_address}, recibido {tx.to}.", {}

            cfg = PRICING_TABLE.get(service, PRICING_TABLE["solve"])
            min_wei = cfg["amount_wei"]
            actual_wei = tx.value

            if actual_wei < min_wei:
                return False, f"Fondos insuficientes. Se requieren {min_wei} wei ({cfg['amount_eth']} ETH), recibidos {actual_wei} wei.", {}

            payer = tx["from"]
            val_eth = float(self.w3.from_wei(actual_wei, "ether"))

            # Registrar transaccion como consumida
            self._save_processed_tx(tx_hash_clean, payer, val_eth, service)

            # Notificar al usuario a Discord
            msg = (
                f"⚡ **¡MICRO-PAGO x402 RECIBIDO ON-CHAIN!**\n\n"
                f"• **Servicio:** `{service.upper()}`\n"
                f"• **Importe:** `{val_eth:.6f} ETH` (~${val_eth * 2600:.2f} USD)\n"
                f"• **Cliente / Payer:** `{payer}`\n"
                f"• **Destino:** `{self.payout_address}` (Tu Coinbase Wallet)\n"
                f"• **Tx Hash:** `{tx_hash_clean}`\n"
                f"• **Basescan:** <https://basescan.org/tx/{tx_hash_clean}>\n\n"
                f"Ingreso directo recibido por demanda externa en el Gateway del Agente."
            )
            notify_user_discord(msg, title="💰 Micro-Pago x402 Recibido", color=0x2ecc71, channel="dashboard")
            notify_user_discord(msg, title="💰 Micro-Pago x402 Recibido", color=0x2ecc71, channel="general")

            return True, "Pago verificado con exito.", {"payer": payer, "value_eth": val_eth, "tx_hash": tx_hash_clean}

        except Exception as e:
            return False, f"Error al verificar transaccion en Base RPC: {e}", {}

_gateway_instance = None

def get_gateway() -> X402Gateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = X402Gateway()
    return _gateway_instance
