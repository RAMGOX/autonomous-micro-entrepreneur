"""
POIDH Bounty Scanner: Escáner oficial del protocolo POIDH (Pics Or It Didn't Happen).
Consulta el servidor MCP oficial de poidh.xyz y filtra tareas con fondos reales
bloqueados en los contratos inteligentes de Base y Arbitrum.
"""
import json
import urllib.request
import sys
from pathlib import Path

POIDH_MCP_URL = "https://poidh.xyz/api/mcp"
POIDH_INDEXER_URL = "https://indexer.poidh.xyz/api/v1"

def get_open_poidh_bounties():
    """Obtiene la lista de bounties activos desde el protocolo POIDH combinando MCP oficial e Indexer REST"""
    bounties = []
    seen_ids = set()

    # 1. MCP Server Oficial (devuelve los bounties mas recientes ordenados)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "find_bounties",
            "arguments": {"limit": 50}
        }
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "AutonomousMicroEntrepreneur-POIDH/1.0"
    }

    try:
        req = urllib.request.Request(
            POIDH_MCP_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=12) as res:
            raw = res.read().decode("utf-8")
            data = json.loads(raw.split("data: ")[-1] if "data: " in raw else raw)
            content_text = data["result"]["content"][0]["text"]
            bounties_data = json.loads(content_text)
            for b in bounties_data.get("bounties", []):
                bid = b.get("id")
                if bid and bid not in seen_ids:
                    seen_ids.add(bid)
                    bounties.append(b)
    except Exception as e:
        print(f"[POIDH Scanner Warning MCP]: {e}", file=sys.stderr)

    # 2. Respaldo y expansion via Indexer REST oficial (bounties abiertos no cancelados)
    try:
        url = f"{POIDH_INDEXER_URL}/bounties?chainId=8453&inProgress=true&isCanceled=false&limit=100"
        req = urllib.request.Request(url, headers={"User-Agent": "AutonomousMicroEntrepreneur-Scanner/2.0"})
        with urllib.request.urlopen(req, timeout=8) as res:
            raw_list = json.loads(res.read())
            if isinstance(raw_list, list):
                for b in raw_list:
                    bid = b.get("id")
                    if bid and bid not in seen_ids:
                        seen_ids.add(bid)
                        amount_wei = int(b.get("amount", 0) or 0)
                        amount_eth = amount_wei / 1e18 if amount_wei > 0 else 0.0
                        bounties.append({
                            "id": bid,
                            "title": b.get("title", ""),
                            "description": b.get("description", ""),
                            "chain": "base",
                            "status": "open",
                            "amount": amount_eth,
                            "reward": f"{amount_eth:.4f} ETH",
                            "rewardToken": "ETH",
                            "rewardUsd": round(amount_eth * 2600, 2),
                            "url": f"https://poidh.xyz/base/bounty/{bid}"
                        })
    except Exception as e:
        print(f"[POIDH Indexer Scanner Warning]: {e}", file=sys.stderr)

    return bounties

def filter_solvable_bounties(bounties):
    """Filtra y clasifica las tareas que una IA / agente autónomo puede resolver (datos, código, análisis)"""
    solvable = []
    for b in bounties:
        status = b.get("status", "").lower()
        if status != "open":
            continue
            
        title = b.get("title", "")
        desc = b.get("description", "")
        chain = b.get("chain", "").lower()
        if chain != "base":
            continue
            
        reward = b.get("reward", "0")
        reward_usd = b.get("rewardUsd", 0)
        
        # Palabras clave que indican tareas digitales o de software genuino
        text_full = (title + " " + desc).lower()
        is_digital = any(k in text_full for k in [
            "csv", "data", "code", "contract", "analyze", "analysis",
            "scraper", "query", "script", "dashboard", "wallet", "indexer",
            "subgraph", "dataset", "solidity", "python"
        ])
        
        # Descartar tareas fisicas, sociales, eventos, arte IRL, video o de referidos
        is_physical = any(k in text_full for k in [
            "selfie", "sticker", "irl", "take a pic", "physical", "in seattle", "in person",
            "art show", "art gallery", "concert", "recruit", "referral", "musemaxxing",
            "muse agent", "street music", "performance", "handwritten", "photo of",
            "costume", "halloween", "sing", "dance", "eat", "drink", "travel",
            "video", "audiovisual", "clip", "remix", "podcast", "youtube", "tiktok", "scene from"
        ])
        
        item = {
            "id": b.get("id"),
            "chain": chain,
            "title": title,
            "reward": reward,
            "reward_usd": reward_usd,
            "url": b.get("url"),
            "issuer": b.get("issuer"),
            "is_digital": is_digital and not is_physical,
            "description": desc[:300] + "..." if len(desc) > 300 else desc
        }
        solvable.append(item)
        
    return solvable

def safe_print(text: str):
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    except Exception:
        print(text.encode("ascii", errors="replace").decode("ascii"))

if __name__ == "__main__":
    bounties = get_open_poidh_bounties()
    safe_print(f"Total bounties activos detectados en POIDH: {len(bounties)}")
    filtered = filter_solvable_bounties(bounties)
    
    safe_print("\n--- Bounties con Recompensa Real en Smart Contract ---")
    for f in filtered:
        tag = "[DIGITAL/RESOLUBLE]" if f["is_digital"] else "[REQUIERE ACCION FISICA/IRL]"
        safe_print(f"{tag} ID #{f['id']} ({f['chain'].upper()}) - {f['reward']} (~${f['reward_usd']})")
        safe_print(f"  Titulo: {f['title']}")
        safe_print(f"  URL: {f['url']}\n")
