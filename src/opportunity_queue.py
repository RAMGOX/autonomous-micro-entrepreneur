"""
Opportunity Queue Manager: Gestor de la cola de oportunidades clasificadas.
Controla el ciclo de vida, clasificación por dificultad (baja, media, alta)
y purga automática con TTL de 2 horas (7200s).
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

def safe_print(text: str):
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    except Exception:
        try:
            print(text.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass

BASE_DIR = Path(__file__).resolve().parent.parent
QUEUE_FILE = BASE_DIR / "memoria" / "estado" / "cola_oportunidades.json"
ARCHIVE_FILE = BASE_DIR / "memoria" / "estado" / "oportunidades_archivadas.json"

MAX_AGE_SECONDS = 7200  # 2 Horas TTL

def load_queue() -> List[Dict[str, Any]]:
    if QUEUE_FILE.exists():
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_queue(items: List[Dict[str, Any]]):
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)

def prune_expired_opportunities() -> int:
    """Purga de la cola activa cualquier tarea que lleve más de 2 horas sin ejecutarse"""
    items = load_queue()
    now = time.time()
    active = []
    expired = []

    for it in items:
        created_at = it.get("created_at", now)
        status = it.get("status", "pending")
        if status == "pending" and (now - created_at) > MAX_AGE_SECONDS:
            it["status"] = "expired"
            it["expired_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            expired.append(it)
        else:
            active.append(it)

    if expired:
        save_queue(active)
        # Guardar en archivo histórico sin saturar la cola activa
        archive = []
        if ARCHIVE_FILE.exists():
            try:
                with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                    archive = json.load(f)
            except Exception:
                pass
        archive.extend(expired)
        # Mantener archivo histórico recortado a 100 items
        archive = archive[-100:]
        with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(archive, f, indent=2, ensure_ascii=False)
        safe_print(f"[Queue] Purgadas {len(expired)} oportunidad(es) expiradas (>2 horas).")

    return len(expired)

def push_opportunity(title: str, url: str, description: str, difficulty: str, estimated_value_usd: float = 0.0, reward_currency: str = "USD", is_escrow_verified: bool = False) -> Dict[str, Any]:
    """Añade una oportunidad clasificada por Ollama local a la cola"""
    prune_expired_opportunities()
    items = load_queue()

    # Evitar duplicados por URL
    for it in items:
        if it.get("url") == url:
            return it

    difficulty = difficulty.lower().strip()
    if difficulty not in ["baja", "media", "alta"]:
        difficulty = "media"

    opp = {
        "id": f"opp_{int(time.time())}_{abs(hash(url)) % 10000}",
        "title": title,
        "url": url,
        "description": description[:1000],
        "difficulty": difficulty,
        "estimated_value_usd": float(estimated_value_usd),
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
    safe_print(f"[Queue] Nueva oportunidad registrada [{difficulty.upper()} | ${estimated_value_usd}]: {title[:40]}...")
    return opp

def get_best_pending_opportunity(difficulty_levels: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Devuelve la oportunidad pendiente más rentable. Si no se especifican niveles, busca en toda la lista (alta, media, baja)"""
    top = get_top_pending_opportunities(difficulty_levels=difficulty_levels, limit=1)
    return top[0] if top else None

def get_cerebro4_opportunities(limit: int = 3, lock: bool = False, solver: str = "Cerebro 4 (Argon)") -> List[Dict[str, Any]]:
    """
    Estrategia Cerebro 4:
    1. Prioridad: nivel 'alta'.
    2. Fallback: si no hay 'alta', toma lote de nivel 'media' y 'baja' más rentables
       para evitar inactividad.
    """
    alta_items = get_top_pending_opportunities(difficulty_levels=["alta"], limit=limit, lock=lock, solver=solver)
    if alta_items:
        return alta_items
    return get_top_pending_opportunities(difficulty_levels=["media", "baja"], limit=limit, lock=lock, solver=solver)

def get_top_pending_opportunities(difficulty_levels: Optional[List[str]] = None, limit: int = 3, lock: bool = False, solver: str = "") -> List[Dict[str, Any]]:
    """Devuelve las top N oportunidades pendientes más rentables y opcionalmente las bloquea para evitar colisiones"""
    prune_expired_opportunities()
    items = load_queue()

    if difficulty_levels:
        levels = [d.lower() for d in difficulty_levels]
    else:
        levels = ["alta", "media", "baja"]

    candidates = [
        it for it in items
        if it.get("status") == "pending" and it.get("difficulty") in levels
    ]
    if not candidates:
        return []

    # Ordenar estrictamente por Rentabilidad ($ USD) descendente primero, luego fecha
    candidates.sort(key=lambda x: (x.get("estimated_value_usd", 0.0), x.get("is_escrow_verified", False), x.get("created_at", 0)), reverse=True)
    selected = candidates[:limit]

    if lock and solver:
        selected_ids = {s["id"] for s in selected}
        for it in items:
            if it.get("id") in selected_ids:
                it["status"] = "in_progress"
                it["solver"] = solver
                it["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_queue(items)

    return selected

def mark_opportunity_in_progress(opp_id: str, solver: str) -> bool:
    items = load_queue()
    found = False
    for it in items:
        if it.get("id") == opp_id:
            it["status"] = "in_progress"
            it["solver"] = solver
            it["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            found = True
            break
    if found:
        save_queue(items)
    return found

def mark_opportunity_executed(opp_id: str, solver: str, solution_path: str = "") -> bool:
    items = load_queue()
    found = False
    for it in items:
        if it.get("id") == opp_id:
            it["status"] = "executed"
            it["solver"] = solver
            it["solution_path"] = solution_path
            it["executed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            found = True
            break
    if found:
        save_queue(items)
    return found

def get_queue_summary() -> Dict[str, Any]:
    """Resumen para el Dashboard y telemetría"""
    prune_expired_opportunities()
    items = load_queue()
    pending = [it for it in items if it.get("status") == "pending"]
    delivered = [it for it in items if it.get("status") == "delivered"]
    executed = [it for it in items if it.get("status") == "executed"]
    escrow_verified = len([it for it in pending if it.get("is_escrow_verified", False)])

    curated_count = 0
    curated_path = BASE_DIR / "memoria" / "datasets_curados" / "oportunidades_grants_verificados.json"
    if curated_path.exists():
        try:
            with open(curated_path, "r", encoding="utf-8") as f:
                curated_count = len(json.load(f))
        except Exception:
            pass

    return {
        "total_active": len(pending),
        "alta": len([it for it in pending if it.get("difficulty") == "alta"]),
        "media": len([it for it in pending if it.get("difficulty") == "media"]),
        "baja": len([it for it in pending if it.get("difficulty") == "baja"]),
        "escrow_verified": escrow_verified,
        "curated_grants": curated_count,
        "executed_total": len(executed) + len(delivered),
        "delivered_total": len(delivered)
    }
