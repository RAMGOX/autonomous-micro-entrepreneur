"""
POIDH Claim Tracker: Monitor autnomo de estado de reclamaciones y cobros on-chain.
Comprueba peridicamente si las entregas enviadas a Base Mainnet han sido
aprobadas por los creadores de las recompensas, registra el cobro
y ejecuta el barrido automtico de fondos hacia la cartera del usuario.
"""
import os
import sys
import json
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from discord_bridge import notify_user_discord
from poidh_claim_submitter import sweep_rewards_to_user, USER_PAYOUT_WALLET

QUEUE_FILE = BASE_DIR / "memoria" / "estado" / "cola_oportunidades.json"
PAID_FILE = BASE_DIR / "memoria" / "estado" / "recompensas_cobradas.json"
POIDH_MCP_URL = "https://poidh.xyz/api/mcp"
POIDH_INDEXER_URL = "https://indexer.poidh.xyz/api/v1"

CHAIN_IDS = {
    "base": 8453,
    "arbitrum": 42161,
    "mainnet": 1
}

OUR_WALLETS = [
    "0x02c1f87f514493F359Afc0B3ff6b587434770361".lower(),
    "0x62472cdc3146ccdf638224c353e7af4d4842875d".lower(),
    USER_PAYOUT_WALLET.lower()
]

def fetch_wallet_claims_direct(chain: str = "base"):
    """Consulta directa y de alta velocidad al indexer REST para todas nuestras carteras"""
    chain_id = CHAIN_IDS.get(chain.lower(), 8453)
    results = []
    for w in OUR_WALLETS:
        try:
            url = f"{POIDH_INDEXER_URL}/claims?chainId={chain_id}&issuer={w}"
            req = urllib.request.Request(url, headers={"User-Agent": "AutonomousMicroEntrepreneur-Tracker/2.0"})
            with urllib.request.urlopen(req, timeout=6) as res:
                items = json.loads(res.read())
                if isinstance(items, list):
                    results.extend(items)
        except Exception as e:
            pass
    return results

def fetch_bounty_onchain_status(chain: str, bounty_id: int):
    # Intentar primero con el indexer REST de alto rendimiento
    chain_id = CHAIN_IDS.get(chain.lower(), 8453)
    try:
        url = f"{POIDH_INDEXER_URL}/bounties/{chain_id}/{int(bounty_id)}"
        req = urllib.request.Request(url, headers={"User-Agent": "AutonomousMicroEntrepreneur-Tracker/2.0"})
        with urllib.request.urlopen(req, timeout=6) as res:
            return json.loads(res.read())
    except Exception:
        pass

    # Fallback al MCP server oficial
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_bounty",
            "arguments": {"chain": chain.lower(), "id": int(bounty_id)}
        }
    }
    req = urllib.request.Request(
        POIDH_MCP_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "AutonomousMicroEntrepreneur-Tracker/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            raw = res.read().decode("utf-8")
            for p in raw.split("data: "):
                p = p.strip()
                if p.startswith("{"):
                    try:
                        d = json.loads(p)
                        if "result" in d:
                            return json.loads(d["result"]["content"][0]["text"])
                    except Exception:
                        pass
    except Exception as e:
        print(f"[Tracker Error] Fallo al consultar bounty #{bounty_id}: {e}", file=sys.stderr)
    return None

def check_active_claims_status():
    """Escanea la cola en busca de tareas claimed_onchain y verifica si fueron aceptadas"""
    if not QUEUE_FILE.exists():
        return 0

    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        return 0

    changed = False
    accepted_count = 0

    # Consulta de alta velocidad en una sola llamada de todas nuestras reclamaciones en Base
    wallet_claims = fetch_wallet_claims_direct("base")
    wallet_claims_by_bounty = {}
    for c in wallet_claims:
        bid = c.get("bountyId")
        if bid:
            wallet_claims_by_bounty[int(bid)] = c

    for it in items:
        status = it.get("status")
        if status != "claimed_onchain":
            continue

        url = it.get("url", "")
        import re
        m = re.search(r"poidh\.xyz/([^/]+)/bounty/([0-9]+)", url)
        if not m:
            continue
        chain = m.group(1).lower()
        bounty_id = int(m.group(2))

        # Chequeo instantaneo en memoria si la reclamacion ya existe en Base
        fast_claim = wallet_claims_by_bounty.get(bounty_id) if chain == "base" else None
        if fast_claim:
            claim_id = fast_claim.get("onChainId")
            is_accepted = fast_claim.get("isAccepted", False)
            it["claim_id"] = claim_id
            if is_accepted and it.get("status") != "payout_received":
                it["status"] = "payout_received"
                it["payout_received_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                changed = True
                accepted_count += 1
                reward_str = it.get("reward_currency", "ETH")
                title = it.get("title", "")
                msg = (
                    f"🎉 **¡RECOMPENSA ACEPTADA Y PAGADA ON-CHAIN!**\n\n"
                    f"• **Bounty:** `{title}`\n"
                    f"• **Recompensa:** `{reward_str}`\n"
                    f"• **Claim ID:** `#{claim_id}`\n"
                    f"• **Red:** `{chain.upper()}`\n\n"
                    f"El creador aprobó la entrega. Activando barrido automático hacia tu cartera: `{USER_PAYOUT_WALLET}`."
                )
                notify_user_discord(msg, title="💰 ¡Pago Aprobado!", color=0x2ecc71, channel="general")
                notify_user_discord(msg, title="💰 ¡Pago Aprobado!", color=0x2ecc71, channel="dashboard")
                sweep_rewards_to_user()
                save_reward_record(it)
            continue

        bounty_data = fetch_bounty_onchain_status(chain, bounty_id)
        if not bounty_data:
            continue

        b_status = bounty_data.get("status", "")
        winning_claim = bounty_data.get("winningClaim")
        claims = bounty_data.get("claims", [])

        # Buscar si alguno de nuestros reclamos fue aceptado
        for cl in claims:
            issuer = (cl.get("issuer") or cl.get("issuerAddress") or "").lower()
            if issuer in OUR_WALLETS:
                claim_id = cl.get("onChainId") or cl.get("claimId")
                is_accepted = cl.get("isAccepted", False) or (winning_claim and winning_claim == claim_id)
                it["claim_id"] = claim_id

                if is_accepted and it.get("status") != "payout_received":
                    it["status"] = "payout_received"
                    it["payout_received_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    changed = True
                    accepted_count += 1

                    reward_str = it.get("reward_currency", "ETH")
                    title = it.get("title", "")

                    # Notificar a Discord (en general y dashboard)
                    msg = (
                        f"🎉 **¡RECOMPENSA ACEPTADA Y PAGADA ON-CHAIN!**\n\n"
                        f"• **Bounty:** `{title}`\n"
                        f"• **Recompensa:** `{reward_str}`\n"
                        f"• **Claim ID:** `#{claim_id}`\n"
                        f"• **Red:** `{chain.upper()}`\n\n"
                        f"El creador aprob la entrega. Activando barrido automtico hacia tu cartera: `{USER_PAYOUT_WALLET}`."
                    )
                    notify_user_discord(msg, title="💰 ¡Pago Aprobado!", color=0x2ecc71, channel="general")
                    notify_user_discord(msg, title="💰 ¡Pago Aprobado!", color=0x2ecc71, channel="dashboard")

                    # Ejecutar barrido inmediato
                    sweep_rewards_to_user()

                    # Guardar registro de recompensa
                    save_reward_record(it)
                    break

    if changed:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

    return accepted_count

def save_reward_record(opp: dict):
    records = []
    if PAID_FILE.exists():
        try:
            with open(PAID_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []
    records.append({
        "id": opp.get("id"),
        "title": opp.get("title"),
        "reward": opp.get("reward_currency"),
        "usd_val": opp.get("estimated_value_usd"),
        "tx_hash": opp.get("tx_hash"),
        "claim_id": opp.get("claim_id"),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    PAID_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PAID_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    count = check_active_claims_status()
    print(f"[Claim Tracker] Reclamaciones aprobadas detectadas en este ciclo: {count}")
