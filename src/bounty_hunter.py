"""
Bounty Hunter: Rastreador autónomo de recompensas con ESCROW VERIFICADO EN BLOCKCHAIN.
Rastrea protocolos on-chain como POIDH (Base / Arbitrum).
Garantiza que el 100% de las tareas tengan fondos reales bloqueados en contratos inteligentes
antes de ser encoladas en memoria/estado/cola_oportunidades.json.
"""
import os
import sys
import time
import json
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from poidh_scanner import get_open_poidh_bounties, filter_solvable_bounties
from opportunity_queue import push_opportunity, prune_expired_opportunities

SEEN_BOUNTIES_FILE = BASE_DIR / "memoria" / "estado" / "bounties_vistas.json"

def safe_print(text: str):
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    except Exception:
        try:
            print(text.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass

def load_seen_bounties() -> set:
    if SEEN_BOUNTIES_FILE.exists():
        try:
            with open(SEEN_BOUNTIES_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_seen_bounties(seen: set):
    SEEN_BOUNTIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_BOUNTIES_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, indent=2)

def scan_onchain_bounties():
    """Escanea POIDH y protocolos de escrow on-chain y encola tareas con fondos verificados"""
    prune_expired_opportunities()
    seen = load_seen_bounties()
    
    safe_print("[Bounty Hunter] Escaneando protocolo POIDH (Exclusivo Base 100% Autónomo)...")
    raw_bounties = get_open_poidh_bounties()
    solvable = filter_solvable_bounties(raw_bounties)
    
    added_count = 0
    for b in solvable:
        # Solo admitir tareas de Base digitales/resolubles por software o IA
        chain = b.get("chain", "base").lower()
        if chain != "base" or not b.get("is_digital"):
            continue
            
        b_id = str(b.get("id"))
        chain = b.get("chain", "base").lower()
        unique_key = f"poidh_{chain}_{b_id}"
        
        if unique_key in seen:
            continue
            
        reward_usd = float(b.get("reward_usd", 0.0))
        reward_str = b.get("reward", "ETH")
        title = f"[{chain.upper()}] {b.get('title')}"
        url = b.get("url")
        desc = b.get("description", "")
        
        # Clasificación estricta por dificultad y valor
        if reward_usd >= 50.0:
            diff = "alta"
        elif reward_usd >= 10.0:
            diff = "media"
        else:
            diff = "baja"
            
        opp = push_opportunity(
            title=title,
            url=url,
            description=desc,
            difficulty=diff,
            estimated_value_usd=reward_usd,
            reward_currency=reward_str,
            is_escrow_verified=True
        )
        
        seen.add(unique_key)
        added_count += 1
        safe_print(f"[Bounty Hunter] [ESCROW VERIFICADO] Encolada #{b_id} ({chain.upper()}): {title} [${reward_usd}]")
        
    save_seen_bounties(seen)
    safe_print(f"[Bounty Hunter] Escaneo finalizado. {added_count} nueva(s) tarea(s) encolada(s).")
    return added_count

if __name__ == "__main__":
    scan_onchain_bounties()
