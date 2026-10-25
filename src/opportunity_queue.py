"""
Opportunity Queue Manager: Gestor atómico y normalizado de oportunidades reales.
Soporta múltiples fuentes: GitHub/Algora Bounties, Apify Ideas, y POIDH filtrado.
Escritura atómica libre de condiciones de carrera y limpieza de esquemas heredados.
"""
import os
import re
import sys
import json
import time
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
QUEUE_FILE = BASE_DIR / "memoria" / "estado" / "cola_oportunidades.json"
ARCHIVE_FILE = BASE_DIR / "memoria" / "estado" / "oportunidades_archivadas.json"

MAX_AGE_SECONDS = 21600  # 6 horas TTL para dar margen a chats paralelos y revisión móvil
_queue_lock = threading.Lock()


def safe_print(text: str):
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    except Exception:
        pass


def _parse_timestamp(val: Any, fallback: float) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            clean = val.strip().replace("Z", "+00:00")
            return datetime.fromisoformat(clean).timestamp()
        except Exception:
            try:
                return float(val)
            except Exception:
                return fallback
    return fallback


def _parse_usd(val: Any) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", val.replace(",", ""))
        if m:
            return float(m.group(1))
    return 0.0


def _normalize_item(it: Dict[str, Any], now: float) -> Dict[str, Any]:
    """Normaliza entradas antiguas con claves en español a un único esquema limpio."""
    if "title" not in it and "titulo" in it:
        it["title"] = it.pop("titulo")
    if "description" not in it and "descripcion" in it:
        it["description"] = it.pop("descripcion")
    if "difficulty" not in it:
        it["difficulty"] = str(it.pop("nivel", "media")).lower()
    if "estimated_value_usd" not in it:
        raw_rew = it.pop("recompensa_estimada_usd", 0.0)
        it["estimated_value_usd"] = _parse_usd(raw_rew)
        if "reward_currency" not in it and isinstance(raw_rew, str):
            it["reward_currency"] = raw_rew
    if "url" not in it or not it["url"]:
        plat = it.get("plataforma", "")
        chain = it.get("cadena", "base")
        bid = it.get("bounty_id")
        if plat == "poidh" and bid:
            it["url"] = f"https://poidh.xyz/{chain}/bounty/{bid}"
        else:
            it["url"] = ""
    if "solution_path" not in it and "solution_file" in it:
        it["solution_path"] = it.pop("solution_file")
    it["created_at"] = _parse_timestamp(it.get("created_at"), now - MAX_AGE_SECONDS - 10)
    if "source" not in it:
        url = it.get("url", "")
        if "github.com" in url or "algora.io" in url:
            it["source"] = "github_bounty"
        elif "poidh.xyz" in url:
            it["source"] = "poidh"
        else:
            it["source"] = "other"
    return it


def _atomic_write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def load_queue() -> List[Dict[str, Any]]:
    if QUEUE_FILE.exists():
        try:
            raw = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                now = time.time()
                return [_normalize_item(dict(x), now) for x in raw if isinstance(x, dict)]
        except Exception:
            pass
    return []


def save_queue(items: List[Dict[str, Any]]):
    with _queue_lock:
        _atomic_write_json(QUEUE_FILE, items)


def prune_expired_opportunities() -> int:
    items = load_queue()
    now = time.time()
    active = []
    expired = []

    for it in items:
        status = it.get("status", "pending")
        created_at = float(it.get("created_at", now))
        ttl = 86400 if it.get("source") == "github_bounty" else MAX_AGE_SECONDS
        if status == "pending" and (now - created_at) > ttl:
            it["status"] = "expired"
            it["expired_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            expired.append(it)
        else:
            active.append(it)

    if expired:
        save_queue(active)
        archive = []
        if ARCHIVE_FILE.exists():
            try:
                archive = json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
                if not isinstance(archive, list):
                    archive = []
            except Exception:
                archive = []
        archive.extend(expired)
        _atomic_write_json(ARCHIVE_FILE, archive[-150:])
    return len(expired)


def push_opportunity(
    title: str,
    url: str,
    description: str,
    difficulty: str,
    estimated_value_usd: float = 0.0,
    reward_currency: str = "USD",
    is_escrow_verified: bool = False,
    source: str = "auto"
) -> Dict[str, Any]:
    prune_expired_opportunities()
    items = load_queue()

    for it in items:
        if url and it.get("url") == url:
            return it

    difficulty = difficulty.lower().strip()
    if difficulty not in ("baja", "media", "alta"):
        difficulty = "media"

    if source == "auto":
        if "github.com" in url or "algora.io" in url:
            source = "github_bounty"
        elif "poidh.xyz" in url:
            source = "poidh"
        else:
            source = "other"

    opp = {
        "id": f"opp_{int(time.time())}_{abs(hash(url or title)) % 10000}",
        "source": source,
        "title": title,
        "url": url,
        "description": description[:1500],
        "difficulty": difficulty,
        "estimated_value_usd": round(float(estimated_value_usd), 2),
        "reward_currency": reward_currency,
        "is_escrow_verified": bool(is_escrow_verified),
        "created_at": time.time(),
        "created_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending",
        "solver": None,
        "solution_path": None
    }
    items.append(opp)
    save_queue(items)
    safe_print(f"[Queue] +Oportunidad [{source} | {difficulty.upper()} | ${estimated_value_usd}]: {title[:55]}")
    return opp


def score_opportunity_cost_benefit(opp: Dict[str, Any]) -> float:
    title = (opp.get("title") or "").lower()
    desc = (opp.get("description") or "").lower()
    text = f"{title} {desc}"
    val_usd = float(opp.get("estimated_value_usd", 0.0))

    unfeasible = [
        "wedgie", "selfie", "sticker", "irl", "ticket", "entry is", "human body",
        "desert", "in person", "recruit", "musemaxxing", "muse agent", "concert",
        "art show", "street music", "referral", "invite", "costume", "halloween",
        "tattoo", "video trailer", "movie trailer", "post on x", "tweet", "tiktok",
        "buy and lock", "buy $"
    ]
    if any(k in text for k in unfeasible):
        return -1000.0

    score = 0.0
    if opp.get("source") == "github_bounty":
        score += 45.0

    tech_keywords = [
        "python", "typescript", "javascript", "solidity", "csv", "dataset",
        "scraper", "api", "bug", "fix", "cli", "sdk", "dashboard", "contract",
        "query", "indexer", "json", "fastapi", "playwright"
    ]
    tech_matches = sum(1 for k in tech_keywords if k in text)
    if tech_matches == 0 and opp.get("source") == "poidh":
        return -500.0

    score += tech_matches * 12.0
    if opp.get("is_escrow_verified"):
        score += 20.0

    if 5.0 <= val_usd <= 1500.0:
        score += min(val_usd, 300.0) * 0.6
    elif val_usd > 0:
        score += 5.0

    return score


def get_best_cost_benefit_opportunity(
    difficulty_levels: Optional[List[str]] = None,
    lock: bool = False,
    solver: str = ""
) -> Optional[Dict[str, Any]]:
    prune_expired_opportunities()
    items = load_queue()
    levels = [d.lower() for d in difficulty_levels] if difficulty_levels else ["alta", "media", "baja"]

    candidates = [
        it for it in items
        if it.get("status") == "pending" and it.get("difficulty") in levels
    ]
    if not candidates:
        return None

    scored = [(it, score_opportunity_cost_benefit(it)) for it in candidates]
    viable = [pair for pair in scored if pair[1] > 0]
    if not viable:
        return None

    viable.sort(key=lambda pair: pair[1], reverse=True)
    best_opp = viable[0][0]

    if lock and solver:
        best_id = best_opp["id"]
        for it in items:
            if it.get("id") == best_id:
                it["status"] = "in_progress"
                it["solver"] = solver
                it["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_queue(items)

    return best_opp


def get_top_pending_opportunities(
    difficulty_levels: Optional[List[str]] = None,
    limit: int = 5,
    lock: bool = False,
    solver: str = ""
) -> List[Dict[str, Any]]:
    prune_expired_opportunities()
    items = load_queue()
    levels = [d.lower() for d in difficulty_levels] if difficulty_levels else ["alta", "media", "baja"]

    candidates = [
        it for it in items
        if it.get("status") == "pending" and it.get("difficulty") in levels and score_opportunity_cost_benefit(it) > 0
    ]
    candidates.sort(key=lambda x: score_opportunity_cost_benefit(x), reverse=True)
    selected = candidates[:limit]

    if lock and solver and selected:
        sel_ids = {s["id"] for s in selected}
        for it in items:
            if it.get("id") in sel_ids:
                it["status"] = "in_progress"
                it["solver"] = solver
                it["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_queue(items)

    return selected


def get_best_pending_opportunity(difficulty_levels: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    top = get_top_pending_opportunities(difficulty_levels=difficulty_levels, limit=1)
    return top[0] if top else None


def get_cerebro4_opportunities(limit: int = 3, lock: bool = False, solver: str = "Argon 4 (Pro)") -> List[Dict[str, Any]]:
    alta = get_top_pending_opportunities(difficulty_levels=["alta"], limit=limit, lock=lock, solver=solver)
    if alta:
        return alta
    return get_top_pending_opportunities(difficulty_levels=["media", "baja"], limit=limit, lock=lock, solver=solver)


def update_opportunity_status(opp_id: str, new_status: str, extra: Optional[Dict[str, Any]] = None) -> bool:
    items = load_queue()
    found = False
    for it in items:
        if it.get("id") == opp_id:
            it["status"] = new_status
            it["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            if extra:
                it.update(extra)
            found = True
            break
    if found:
        save_queue(items)
    return found


def mark_opportunity_in_progress(opp_id: str, solver: str) -> bool:
    return update_opportunity_status(opp_id, "in_progress", {
        "solver": solver,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S")
    })


def mark_opportunity_executed(opp_id: str, solver: str, solution_path: str = "", extra: Optional[Dict[str, Any]] = None) -> bool:
    data = {
        "solver": solver,
        "solution_path": solution_path,
        "executed_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    if extra:
        data.update(extra)
    return update_opportunity_status(opp_id, "pending_review", data)


def get_queue_summary() -> Dict[str, Any]:
    prune_expired_opportunities()
    items = load_queue()
    pending = [it for it in items if it.get("status") == "pending" and score_opportunity_cost_benefit(it) > 0]
    in_review = [it for it in items if it.get("status") == "pending_review"]
    claimed = [it for it in items if it.get("status") == "claimed_onchain"]
    paid = [it for it in items if it.get("status") == "payout_received"]
    lost = [it for it in items if it.get("status") in ("closed_lost", "voting_closed")]

    return {
        "total_active": len(pending),
        "alta": len([it for it in pending if it.get("difficulty") == "alta"]),
        "media": len([it for it in pending if it.get("difficulty") == "media"]),
        "baja": len([it for it in pending if it.get("difficulty") == "baja"]),
        "github_bounties": len([it for it in pending if it.get("source") == "github_bounty"]),
        "poidh_bounties": len([it for it in pending if it.get("source") == "poidh"]),
        "pending_review": len(in_review),
        "active_claims": len(claimed),
        "paid_total": len(paid),
        "lost_total": len(lost)
    }
