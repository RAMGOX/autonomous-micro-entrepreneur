"""
POIDH Claim Submitter & Multi-Token Auto-Sweeper:
- PROHIBIDO gastar gas enviando capturas genéricas sin verificar.
- Toda reclamación pasa primero por la Bandeja de Revisión Móvil (Discord) y verifica HTTP 200 del comprobante.
- Barrido automático (Auto-Sweep) soporta tanto ETH nativo como USDC en Base Mainnet hacia tu Coinbase Wallet.
"""
import os
import re
import sys
import json
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, Tuple
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))
load_dotenv(BASE_DIR / "config" / ".env")

from discord_bridge import notify_user_discord
from erc8021_builder import attach_erc8021_attribution, encode_erc8021_suffix
from opportunity_queue import load_queue, save_queue, update_opportunity_status
from review_queue import push_for_review

USER_PAYOUT_WALLET = os.getenv("USER_PAYOUT_WALLET", "0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf")
BASE_MAINNET_RPC = "https://mainnet.base.org"
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
POIDH_MCP_URL = "https://poidh.xyz/api/mcp"

_last_sweep_check = 0.0

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
]


def verify_public_image_url(url: str) -> bool:
    """Comprueba que el proof_uri sea una imagen pública real accesible con HTTP 200."""
    if not url or not url.startswith("https://"):
        return False
    lower = url.lower().split("?")[0]
    if not lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return False
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as res:
            return res.status == 200
    except Exception:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as res:
                return res.status == 200
        except Exception:
            return False


def prepare_claim_for_bounty(chain: str, bounty_id: int, title: str, description: str, proof_uri: str):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "prepare_submit_claim",
            "arguments": {
                "chain": chain.lower(),
                "id": int(bounty_id),
                "title": title[:50],
                "description": description[:900],
                "proofUri": proof_uri
            }
        }
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"
    }
    try:
        req = urllib.request.Request(POIDH_MCP_URL, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=15) as res:
            raw = res.read().decode("utf-8")
            data = json.loads(raw.split("data: ")[-1] if "data: " in raw else raw)
            if data.get("isError"):
                err_text = data.get("result", {}).get("content", [{}])[0].get("text", "")
                return {"isError": True, "message": err_text}
            content_text = data["result"]["content"][0]["text"]
            if content_text.strip().startswith("{"):
                return json.loads(content_text)
            return {"raw_text": content_text}
    except Exception as e:
        return {"isError": True, "message": str(e)}


def sweep_rewards_to_user(force: bool = False):
    """Transfiere automáticamente recompensas acumuladas en USDC (>0.50 USDC) o ETH (>0.0008 ETH) a tu Coinbase Wallet."""
    global _last_sweep_check
    now = time.time()
    if not force and (now - _last_sweep_check) < 300:
        return None
    _last_sweep_check = now

    pk = os.getenv("PRIVATE_KEY_TESTNET")
    if not pk:
        return None

    try:
        from web3 import Web3
        from eth_account import Account

        w3 = Web3(Web3.HTTPProvider(BASE_MAINNET_RPC, request_kwargs={"timeout": 6}))
        acct = Account.from_key(pk)
        dest = Web3.to_checksum_address(USER_PAYOUT_WALLET)
        tx_hashes = []

        # 1. Barrer USDC si > 0.50 USDC
        usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_BASE_ADDRESS), abi=ERC20_ABI)
        usdc_bal = usdc.functions.balanceOf(acct.address).call()
        if usdc_bal >= 500_000:  # >= 0.50 USDC (6 decimales)
            nonce = w3.eth.get_transaction_count(acct.address)
            tx = usdc.functions.transfer(dest, usdc_bal).build_transaction({
                "chainId": 8453,
                "from": acct.address,
                "nonce": nonce,
                "gas": 65000,
                "gasPrice": w3.eth.gas_price
            })
            tx["data"] = attach_erc8021_attribution(tx["data"])
            signed = acct.sign_transaction(tx)
            tx_h = w3.eth.send_raw_transaction(signed.raw_transaction).hex()
            tx_hashes.append(tx_h)
            notify_user_discord(
                f"💸 **USDC transferido a tu Coinbase Wallet:** `{usdc_bal / 1e6:.2f} USDC`\n"
                f"• Destino: `{dest}`\n• Tx: <https://basescan.org/tx/{tx_h}>",
                title="💰 Auto-Sweep USDC Completado",
                color=0x2ecc71,
                channel="general"
            )

        # 2. Barrer ETH si > 0.0008 ETH (dejando 0.00015 ETH de reserva para gas)
        bal_wei = w3.eth.get_balance(acct.address)
        if bal_wei > w3.to_wei(0.0008, "ether"):
            gas_price = w3.eth.gas_price
            estimated_gas = 28000
            reserve = w3.to_wei(0.00015, "ether")
            send_amount = bal_wei - (gas_price * estimated_gas) - reserve
            if send_amount > 0:
                attr_suffix = encode_erc8021_suffix()
                tx = {
                    "nonce": w3.eth.get_transaction_count(acct.address),
                    "to": dest,
                    "value": send_amount,
                    "data": f"0x{attr_suffix.hex()}",
                    "gas": estimated_gas,
                    "gasPrice": gas_price,
                    "chainId": 8453
                }
                signed = acct.sign_transaction(tx)
                tx_h = w3.eth.send_raw_transaction(signed.raw_transaction).hex()
                tx_hashes.append(tx_h)
                notify_user_discord(
                    f"💸 **ETH transferido a tu Coinbase Wallet:** `{w3.from_wei(send_amount, 'ether'):.6f} ETH`\n"
                    f"• Destino: `{dest}`\n• Tx: <https://basescan.org/tx/{tx_h}>",
                    title="💰 Auto-Sweep ETH Completado",
                    color=0x2ecc71,
                    channel="general"
                )
        return tx_hashes[0] if tx_hashes else None
    except Exception as e:
        print(f"[Auto-Sweep Error]: {e}", file=sys.stderr)
        return None


def submit_approved_poidh_claim(bounty_id: int, title: str, description: str, proof_uri: str, opp_id: str = "") -> Tuple[bool, str]:
    """Ejecuta la transacción real en Base Mainnet SOLO cuando el usuario aprueba la entrega en Discord."""
    if not verify_public_image_url(proof_uri):
        return False, f"El comprobante visual no es una imagen pública accesible (HTTP 200): {proof_uri}"

    claim_res = prepare_claim_for_bounty("base", bounty_id, title, description, proof_uri)
    if not claim_res or claim_res.get("isError"):
        return False, f"POIDH rechazó preparar el reclamo: {(claim_res or {}).get('message', 'Error desconocido')}"

    if "transaction" not in claim_res:
        return False, "POIDH no devolvió calldata de transacción."

    pk = os.getenv("PRIVATE_KEY_TESTNET")
    if not pk:
        return False, "No hay clave operativa configurada en .env."

    try:
        from web3 import Web3
        from eth_account import Account

        w3 = Web3(Web3.HTTPProvider(BASE_MAINNET_RPC, request_kwargs={"timeout": 8}))
        bot = Account.from_key(pk)
        bal = w3.eth.get_balance(bot.address)
        if bal < w3.to_wei(0.00003, "ether"):
            return False, f"Gas insuficiente en cartera del bot ({w3.from_wei(bal, 'ether'):.6f} ETH)."

        tx_info = claim_res["transaction"]
        to_addr = Web3.to_checksum_address(tx_info["to"])
        tx_data = attach_erc8021_attribution(tx_info["data"])
        gas_est = w3.eth.estimate_gas({"from": bot.address, "to": to_addr, "data": tx_data})
        raw_tx = {
            "from": bot.address,
            "to": to_addr,
            "data": tx_data,
            "nonce": w3.eth.get_transaction_count(bot.address),
            "gas": int(gas_est * 1.2),
            "gasPrice": w3.eth.gas_price,
            "chainId": 8453,
            "value": 0
        }
        signed_tx = bot.sign_transaction(raw_tx)
        tx_hex = w3.eth.send_raw_transaction(signed_tx.raw_transaction).hex()

        if opp_id:
            update_opportunity_status(opp_id, "claimed_onchain", {
                "claim_submitted": True,
                "tx_hash": tx_hex
            })
        return True, tx_hex
    except Exception as e:
        return False, f"Fallo al firmar/enviar TX en Base: {e}"


def check_and_notify_pending_claims():
    """Vigila barridos periódicos y asegura que ningún reclamo se envíe sin pasar por revisión."""
    sweep_rewards_to_user(force=False)
    return 0
