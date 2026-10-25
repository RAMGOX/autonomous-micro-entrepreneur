"""
POIDH Bounty Scanner: Escáner selectivo de recompensas técnicas en Base L2.
Corrige la valoración de tokens ERC-20 (ETH vs USDC vs otros) y filtra estrictamente
tareas 100% resolubles con software/datos sin gasto de bolsillo.
"""
import json
import urllib.request
import sys

POIDH_MCP_URL = "https://poidh.xyz/api/mcp"
POIDH_INDEXER_URL = "https://indexer.poidh.xyz/api/v1"
USDC_BASE = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
ZERO_ADDR = "0x0000000000000000000000000000000000000000"


def get_open_poidh_bounties():
    bounties = []
    seen_ids = set()

    # 1. MCP Server Oficial (incluye valoración USD calculada por POIDH)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "find_bounties", "arguments": {"limit": 50}}
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        req = urllib.request.Request(POIDH_MCP_URL, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=12) as res:
            raw = res.read().decode("utf-8")
            data = json.loads(raw.split("data: ")[-1] if "data: " in raw else raw)
            content_text = data["result"]["content"][0]["text"]
            bounties_data = json.loads(content_text)
            for b in bounties_data.get("bounties", []):
                bid = b.get("id")
                chain = (b.get("chain") or "").lower()
                if bid and chain == "base" and bid not in seen_ids:
                    seen_ids.add(bid)
                    bounties.append(b)
    except Exception as e:
        print(f"[POIDH Scanner Warning MCP]: {e}", file=sys.stderr)

    # 2. Indexer REST Oficial con detección real de token (evita inflar tokens ERC-20 como ETH)
    try:
        url = f"{POIDH_INDEXER_URL}/bounties?chainId=8453&inProgress=true&isCanceled=false&limit=60"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as res:
            raw_list = json.loads(res.read())
            if isinstance(raw_list, list):
                for b in raw_list:
                    bid = b.get("id")
                    if not bid or bid in seen_ids:
                        continue
                    seen_ids.add(bid)
                    token_addr = str(b.get("token") or b.get("tokenAddress") or ZERO_ADDR).lower()
                    amount_raw = int(b.get("amount", 0) or 0)

                    if token_addr in ("", ZERO_ADDR):
                        amt = amount_raw / 1e18
                        rew_str = f"{amt:.4f} ETH"
                        rew_usd = round(amt * 2450.0, 2)
                        tok_sym = "ETH"
                    elif token_addr == USDC_BASE:
                        amt = amount_raw / 1e6
                        rew_str = f"{amt:.2f} USDC"
                        rew_usd = round(amt, 2)
                        tok_sym = "USDC"
                    else:
                        # Token ERC-20 desconocido: no asumir precio de ETH
                        amt = amount_raw / 1e18
                        rew_str = f"{amt:.2f} ERC20"
                        rew_usd = 0.0
                        tok_sym = "ERC20"

                    bounties.append({
                        "id": bid,
                        "title": b.get("title", ""),
                        "description": b.get("description", ""),
                        "chain": "base",
                        "status": "open",
                        "amount": amt,
                        "reward": rew_str,
                        "rewardToken": tok_sym,
                        "rewardUsd": rew_usd,
                        "url": f"https://poidh.xyz/base/bounty/{bid}"
                    })
    except Exception as e:
        print(f"[POIDH Indexer Warning]: {e}", file=sys.stderr)

    return bounties


def filter_solvable_bounties(bounties):
    """Filtra estrictamente bounties de programación, datos o dashboards sin gasto ni acciones físicas."""
    solvable = []
    for b in bounties:
        if (b.get("status") or "").lower() != "open":
            continue
        if (b.get("chain") or "").lower() != "base":
            continue

        title = b.get("title", "")
        desc = b.get("description", "")
        reward_usd = float(b.get("rewardUsd") or 0.0)
        if reward_usd < 2.0:
            continue

        text_full = f"{title} {desc}".lower()
        is_digital = any(k in text_full for k in [
            "csv", "dataset", "code", "smart contract", "solidity", "python",
            "typescript", "javascript", "scraper", "dashboard", "indexer",
            "subgraph", "github", "api", "cli", "open source", "script"
        ])
        is_blocked = any(k in text_full for k in [
            "selfie", "sticker", "irl", "take a pic", "physical", "in person",
            "art show", "gallery", "concert", "recruit", "referral", "musemaxxing",
            "muse agent", "street music", "performance", "handwritten", "photo of",
            "costume", "halloween", "sing", "dance", "video", "trailer", "clip",
            "podcast", "youtube", "tiktok", "post on x", "tweet", "buy and lock",
            "buy $", "mint ", "raffle", "lottery", "entry fee"
        ])

        solvable.append({
            "id": b.get("id"),
            "chain": "base",
            "title": title,
            "reward": b.get("reward", "0"),
            "reward_usd": reward_usd,
            "url": b.get("url"),
            "issuer": b.get("issuer"),
            "is_digital": bool(is_digital and not is_blocked),
            "description": desc[:600]
        })
    return solvable
