"""
POIDH Claim Tracker: Monitor honesto de reclamaciones y cobros reales en Base Mainnet.
- Repara el bug dict.append en recompensas_cobradas.json.
- Marca automáticamente como 'closed_lost' los bounties que cerraron pagando a otro participante.
- Si detecta aceptación real ('isAccepted == True'), ejecuta barrido inmediato de ETH y USDC.
"""
import os
import re
import sys
import json
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from discord_bridge import notify_user_discord
from poidh_claim_submitter import sweep_rewards_to_user, USER_PAYOUT_WALLET
from opportunity_queue import load_queue, save_queue

PAID_FILE = BASE_DIR / "memoria" / "estado" / "recompensas_cobradas.json"
POIDH_INDEXER_URL = "https://indexer.poidh.xyz/api/v1"

OUR_WALLETS = [
    "0x02c1f87f514493f359afc0b3ff6b587434770361",
    "0x62472cdc3146ccdf638224c353e7af4d4842875d",
    USER_PAYOUT_WALLET.lower()
]


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as res:
        return json.loads(res.read().decode("utf-8"))


def fetch_wallet_claims_direct():
    results = []
    for w in OUR_WALLETS:
        try:
            items = _get_json(f"{POIDH_INDEXER_URL}/claims?chainId=8453&issuer={w}")
            if isinstance(items, list):
                results.extend(items)
        except Exception:
            pass
    return results


def save_reward_record(opp: dict):
    """Guarda cobros reales verificados en estructura consistente (sin romper si el JSON era dict)."""
    state = {
        "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
        "real_usd_earned": 0.0,
        "payouts": []
    }
    if PAID_FILE.exists():
        try:
            raw = json.loads(PAID_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("payouts"), list):
                state = raw
            elif isinstance(raw, list):
                state["payouts"] = raw
        except Exception:
            pass

    usd_val = float(opp.get("estimated_value_usd") or 0.0)
    state["payouts"].append({
        "id": opp.get("id"),
        "title": opp.get("title"),
        "reward": opp.get("reward_currency"),
        "usd_val": usd_val,
        "tx_hash": opp.get("tx_hash"),
        "claim_id": opp.get("claim_id"),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    state["real_usd_earned"] = round(sum(float(p.get("usd_val") or 0.0) for p in state["payouts"]), 2)
    state["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
    PAID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PAID_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def check_active_claims_status():
    items = load_queue()
    if not items:
        return 0

    changed = False
    accepted_count = 0

    wallet_claims = fetch_wallet_claims_direct()
    claims_by_bounty = {}
    for c in wallet_claims:
        bid = c.get("bountyId")
        if bid is not None:
            claims_by_bounty.setdefault(int(bid), []).append(c)

    for it in items:
        if it.get("status") != "claimed_onchain":
            continue

        url = it.get("url", "")
        m = re.search(r"poidh\.xyz/([^/]+)/bounty/([0-9]+)", url)
        if not m:
            continue
        chain = m.group(1).lower()
        bounty_id = int(m.group(2))
        if chain != "base":
            continue

        our_bounty_claims = claims_by_bounty.get(bounty_id, [])
        won_claim = next((c for c in our_bounty_claims if c.get("isAccepted")), None)

        if won_claim:
            claim_id = won_claim.get("onChainId")
            it["claim_id"] = claim_id
            it["status"] = "payout_received"
            it["payout_received_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            changed = True
            accepted_count += 1

            save_reward_record(it)
            sweep_rewards_to_user(force=True)

            msg = (
                f"🎉 **¡RECOMPENSA ACEPTADA Y COBRADA EN BASE!**\n\n"
                f"• **Bounty:** `{it.get('title')}`\n"
                f"• **Importe:** `{it.get('reward_currency')}` (~`${it.get('estimated_value_usd')}`)\n"
                f"• **Claim ID:** `#{claim_id}`\n"
                f"• **Destino:** `{USER_PAYOUT_WALLET}`"
            )
            notify_user_discord(msg, title="💰 ¡Pago Real Recibido!", color=0x2ecc71, channel="general")
            continue

        # Verificar si el bounty ya se cerró o canceló sin aceptar nuestro claim
        try:
            binfo = _get_json(f"{POIDH_INDEXER_URL}/bounties/8453/{bounty_id}")
            if isinstance(binfo, dict):
                in_progress = binfo.get("inProgress", True)
                is_canceled = binfo.get("isCanceled", False)
                if not in_progress or is_canceled:
                    it["status"] = "closed_lost"
                    it["closed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    changed = True
        except Exception:
            pass

    if changed:
        save_queue(items)

    return accepted_count


if __name__ == "__main__":
    print("Claims actualizados. Ganados nuevos:", check_active_claims_status())
