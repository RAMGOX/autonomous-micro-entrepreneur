"""
Unified Bounty Hunter: Combina el escaneo selectivo de POIDH (solo software real en Base)
con el Motor 1 de Bounties de Código en GitHub (Algora / Opire).
"""
import json
import time
from pathlib import Path
from poidh_scanner import get_open_poidh_bounties, filter_solvable_bounties
from github_bounty_hunter import scan_github_bounties
from opportunity_queue import push_opportunity

BASE_DIR = Path(__file__).resolve().parent.parent
SEEN_FILE = BASE_DIR / "memoria" / "estado" / "bounties_vistas.json"

_last_gh_scan = 0.0


def load_seen_bounties() -> set:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def save_seen_bounties(seen: set):
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(sorted(list(seen))[-500:], indent=2), encoding="utf-8")


def scan_onchain_bounties() -> int:
    global _last_gh_scan
    added_count = 0

    # 1. Radar POIDH (solo tareas estrictamente digitales en Base)
    seen = load_seen_bounties()
    raw_bounties = get_open_poidh_bounties()
    solvable = filter_solvable_bounties(raw_bounties)

    for b in solvable:
        if not b.get("is_digital"):
            continue
        b_id = b["id"]
        unique_key = f"base_{b_id}"
        if unique_key in seen:
            continue

        reward_usd = float(b.get("reward_usd") or 0.0)
        diff = "alta" if reward_usd >= 50.0 else ("media" if reward_usd >= 12.0 else "baja")

        push_opportunity(
            title=f"[POIDH BASE] {b['title']}",
            url=b["url"],
            description=b["description"],
            difficulty=diff,
            estimated_value_usd=reward_usd,
            reward_currency=b["reward"],
            is_escrow_verified=True,
            source="poidh"
        )
        seen.add(unique_key)
        added_count += 1

    save_seen_bounties(seen)

    # 2. Radar GitHub / Algora cada 15 minutos para respetar límites de API
    now = time.time()
    if (now - _last_gh_scan) >= 900:
        _last_gh_scan = now
        gh_found = scan_github_bounties(max_enqueue=4)
        added_count += len(gh_found)

    return added_count


if __name__ == "__main__":
    print("Total oportunidades detectadas:", scan_onchain_bounties())
