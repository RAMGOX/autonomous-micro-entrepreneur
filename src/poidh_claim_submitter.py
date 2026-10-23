"""
POIDH Claim Submitter: Gestor de reclamaciones y cobros on-chain.
Toma los entregables resueltos por DeepSeek o Antigravity (Cerebro 4),
prepara la transacción oficial contra el contrato inteligente PoidhV3 en Base (8453)
y genera los datos de firma o enlace de aprobación inmediata hacia Discord.
"""
import os
import re
import json
import urllib.request
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from discord_bridge import notify_user_discord

USER_PAYOUT_WALLET = os.getenv("USER_PAYOUT_WALLET", "0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf")
BASE_MAINNET_RPC = "https://mainnet.base.org"
POIDH_V3_BASE = "0x5555fa783936c260f77385b4e153b9725fef1719"
POIDH_MCP_URL = "https://poidh.xyz/api/mcp"
QUEUE_FILE = BASE_DIR / "memoria" / "estado" / "cola_oportunidades.json"

def extract_poidh_details(opp: dict):
    url = opp.get("url", "")
    match = re.search(r"poidh\.xyz/([^/]+)/bounty/([0-9]+)", url)
    if match:
        return match.group(1).lower(), int(match.group(2))
    return None, None

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
                "description": description[:1000],
                "proofUri": proof_uri
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        req = urllib.request.Request(
            POIDH_MCP_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            raw = res.read().decode("utf-8")
            data = json.loads(raw.split("data: ")[-1] if "data: " in raw else raw)
            if data.get("isError"):
                err_text = data.get("result", {}).get("content", [{}])[0].get("text", "")
                print(f"[POIDH Claim Notice]: {err_text}", file=sys.stderr)
                return {"isError": True, "message": err_text}
            content_text = data["result"]["content"][0]["text"]
            if content_text.strip().startswith("{"):
                return json.loads(content_text)
            return {"raw_text": content_text}
    except Exception as e:
        print(f"[POIDH Claim Error]: {e}", file=sys.stderr)
        return None

def sweep_rewards_to_user():
    """Si la cartera del bot acumula fondos de recompensas en Base (> 0.0008 ETH), transfiere automaticamente el 100% a la cartera del usuario"""
    try:
        from web3 import Web3
        from eth_account import Account
        pk = os.getenv("PRIVATE_KEY_TESTNET")
        if not pk:
            return None
        w3 = Web3(Web3.HTTPProvider(BASE_MAINNET_RPC, request_kwargs={'headers': {'User-Agent': 'Mozilla/5.0'}}))
        acct = Account.from_key(pk)
        bal_wei = w3.eth.get_balance(acct.address)
        
        min_threshold = w3.to_wei(0.0008, "ether")
        if bal_wei > min_threshold:
            gas_price = w3.eth.gas_price
            estimated_gas = 21000
            tx_cost = gas_price * estimated_gas
            reserve = w3.to_wei(0.0001, "ether") # reserva para futuros reclamos
            send_amount = bal_wei - tx_cost - reserve
            if send_amount > 0:
                tx = {
                    "nonce": w3.eth.get_transaction_count(acct.address),
                    "to": Web3.to_checksum_address(USER_PAYOUT_WALLET),
                    "value": send_amount,
                    "gas": estimated_gas,
                    "gasPrice": gas_price,
                    "chainId": 8453
                }
                signed = acct.sign_transaction(tx)
                tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                notify_user_discord(
                    f"🎉 **¡FONDOS TRANSFERIDOS AUTOMÁTICAMENTE!**\n\n"
                    f"• **Cantidad:** `{w3.from_wei(send_amount, 'ether')} ETH`\n"
                    f"• **Destino (Tu Cartera):** `{USER_PAYOUT_WALLET}`\n"
                    f"• **Tx Hash:** `{tx_hash.hex()}`\n\n"
                    f"El bot barrió la recompensa y la depositó directamente en tu Coinbase Wallet.",
                    title="💸 Depósito Automático Completado",
                    color=0x2ecc71
                )
                print(f"[Auto-Sweep] Transferidos {w3.from_wei(send_amount, 'ether')} ETH a {USER_PAYOUT_WALLET}")
                return tx_hash.hex()
    except Exception as e:
        print(f"[Auto-Sweep Error]: {e}", file=sys.stderr)
    return None

def check_and_notify_pending_claims():
    """Revisa cola_oportunidades.json y para cualquier tarea 'executed' sin sign_url, prepara la reclamación y notifica a Discord"""
    sweep_rewards_to_user()
    if not QUEUE_FILE.exists():
        return 0
        
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        return 0
        
    changed = False
    notified_count = 0
    
    for it in items:
        # Tareas ejecutadas pero que aún no han recibido enlace de firma
        if it.get("status") == "executed" and not it.get("sign_url") and not it.get("claim_submitted"):
            chain, bounty_id = extract_poidh_details(it)
            if not chain or not bounty_id:
                continue
                
            title = it.get("title", "")
            raw_desc = it.get("description", "")
            text_full = (title + " " + raw_desc).lower()
            
            # Bloqueo estricto de tareas fisicas, video, audio o referidos
            if any(k in text_full for k in [
                "art show", "art gallery", "concert", "recruit", "referral", "musemaxxing",
                "muse agent", "street music", "performance", "selfie", "sticker", "irl",
                "take a pic", "physical", "in seattle", "in person", "handwritten", "photo of",
                "costume", "halloween", "sing", "dance", "video", "audiovisual", "clip", "remix", "podcast"
            ]):
                print(f"[Claim Submitter] Omitiendo bounty #{bounty_id} por ser tarea fisica/social no apta para software.")
                it["status"] = "discarded_unsolvable"
                changed = True
                continue
                
            clean_title = re.sub(r"^\[[^\]]+\]\s*", "", title)
            # Acortar descripción para evitar URLs gigantescas o caracteres rotos
            raw_desc = it.get("description", "")
            clean_desc = (re.sub(r"[\r\n\t]+", " ", raw_desc)[:100].strip() + f" | Payout: {USER_PAYOUT_WALLET}")[:250]
            proof_uri = "https://github.com/RAMGOX/autonomous-micro-entrepreneur"
            
            claim_res = prepare_claim_for_bounty(
                chain=chain,
                bounty_id=bounty_id,
                title=clean_title,
                description=clean_desc,
                proof_uri=proof_uri
            )
            
            if claim_res and claim_res.get("isError"):
                err_msg = claim_res.get("message", "")
                if "is voting" in err_msg or "not open" in err_msg:
                    print(f"[Claim Submitter] Bounty #{bounty_id} cerrado o en fase de votacion ({err_msg}).")
                    it["status"] = "voting_closed"
                    changed = True
                    continue

            # Si es en Base y la cartera del bot tiene gas, enviar transaccion directamente ON-CHAIN
            if chain == "base" and claim_res and "transaction" in claim_res:
                try:
                    from web3 import Web3
                    from eth_account import Account
                    pk = os.getenv("PRIVATE_KEY_TESTNET")
                    if pk:
                        w3 = Web3(Web3.HTTPProvider(BASE_MAINNET_RPC, request_kwargs={'headers': {'User-Agent': 'Mozilla/5.0'}}))
                        bot = Account.from_key(pk)
                        bal = w3.eth.get_balance(bot.address)
                        min_gas = w3.to_wei(0.00003, "ether")
                        if bal >= min_gas:
                            tx_info = claim_res["transaction"]
                            to_addr = Web3.to_checksum_address(tx_info["to"])
                            tx_data = tx_info["data"]
                            gas_est = w3.eth.estimate_gas({'from': bot.address, 'to': to_addr, 'data': tx_data})
                            gas_price = w3.eth.gas_price
                            nonce = w3.eth.get_transaction_count(bot.address)
                            raw_tx = {
                                "from": bot.address,
                                "to": to_addr,
                                "data": tx_data,
                                "nonce": nonce,
                                "gas": int(gas_est * 1.2),
                                "gasPrice": gas_price,
                                "chainId": 8453,
                                "value": 0
                            }
                            signed_tx = bot.sign_transaction(raw_tx)
                            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                            tx_hex = tx_hash.hex()
                            it["status"] = "claimed_onchain"
                            it["claim_submitted"] = True
                            it["tx_hash"] = tx_hex
                            changed = True
                            notified_count += 1
                            notify_user_discord(
                                f"🤖 **¡RECLAMO ENVIADO AUTOMÁTICAMENTE ON-CHAIN!**\n\n"
                                f"• **Tarea:** `{clean_title}`\n"
                                f"• **Cadena:** `BASE MAINNET`\n"
                                f"• **Recompensa:** `{it.get('reward_currency')} (~${it.get('estimated_value_usd')} USD)`\n"
                                f"• **Cerebro Ejecutor:** `{it.get('solver', 'Cerebro 3 (DeepSeek API)')}`\n"
                                f"• **Tx Hash:** `{tx_hex}`\n"
                                f"• **Basescan:** <https://basescan.org/tx/{tx_hex}>\n\n"
                                f"⚡ Reclamo enviado 100% en automático por el bot. Cuando el creador lo apruebe, el bot transferirá los fondos a tu cartera `{USER_PAYOUT_WALLET}`.",
                                title="⚡ Reclamo Automático en Base",
                                color=0x3498db
                            )
                            print(f"[Claim Submitter] Reclamo automático enviado a Base para bounty #{bounty_id}: {tx_hex}")
                            continue
                except Exception as e:
                    print(f"[Direct Claim Error]: {e}, recurriendo a enlace de firma.", file=sys.stderr)

            if claim_res and claim_res.get("signUrl"):
                raw_url = claim_res["signUrl"]
                # Escapar paréntesis para que Discord no corte el enlace de markdown
                safe_url = raw_url.replace("(", "%28").replace(")", "%29")
                it["sign_url"] = safe_url
                changed = True
                notified_count += 1
                
                notify_user_discord(
                    f"🎯 **¡NUEVA TAREA RESUELTA LISTA PARA COBRAR!**\n\n"
                    f"• **Tarea:** `{clean_title}`\n"
                    f"• **Cadena:** `{chain.upper()}`\n"
                    f"• **Recompensa:** `{it.get('reward_currency')} (~${it.get('estimated_value_usd')} USD)`\n"
                    f"• **Resuelta por:** `{it.get('solver', 'Agente Autónomo')}`\n\n"
                    f"👉 **[PULSA AQUÍ PARA FIRMAR Y COBRAR EN 1 CLIC](<{safe_url}>)**\n\n"
                    f"🔗 *Enlace directo:* <{safe_url}>",
                    title="💰 Tarea Resuelta — Enlace de Cobro Listo",
                    color=0x2ecc71
                )
                print(f"[Claim Submitter] Notificación enviada a Discord para bounty #{bounty_id}")
                
    if changed:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
            
    return notified_count

if __name__ == "__main__":
    count = check_and_notify_pending_claims()
    print(f"Reclamaciones notificadas: {count}")
