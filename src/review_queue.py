"""
Review Queue (Human-in-the-Loop Mobile Approval):
Gestiona bandeja_revision.json para que el usuario apruebe, revise, pida cambios
o descarte trabajos terminados directamente desde botones en Discord o desde el Dashboard móvil.
"""
import os
import json
import time
import tempfile
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
REVIEW_FILE = BASE_DIR / "memoria" / "estado" / "bandeja_revision.json"
OBS_REVIEW_MD = BASE_DIR / "memoria" / "ENTREGAS_PARA_REVISAR.md"
_review_lock = threading.Lock()


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


def load_reviews() -> List[Dict[str, Any]]:
    if REVIEW_FILE.exists():
        try:
            data = json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _sync_obsidian_markdown(items: List[Dict[str, Any]]):
    """Mantiene actualizado un índice limpio en Obsidian con las entregas pendientes y aprobadas."""
    try:
        pending = [x for x in items if x.get("status") == "pending_review"]
        recent_done = [x for x in items if x.get("status") in ("approved", "sent", "changes_requested")][-10:]

        lines = [
            "# 📱 Bandeja de Revisión Móvil (Human-in-the-Loop)",
            f"- **Actualizado:** `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
            f"- **Pendientes de tu OK en Discord:** `{len(pending)}`\n",
            "## ⏳ Pendientes de Aprobación"
        ]
        if not pending:
            lines.append("_No hay entregas esperando aprobación en este momento._\n")
        else:
            for p in pending:
                lines.append(f"### [{p.get('category', 'tarea').upper()}] {p.get('title')}")
                lines.append(f"- **ID:** `{p.get('id')}` | **Valor Est.:** `{p.get('reward_display', '$0')}`")
                lines.append(f"- **Origen:** {p.get('source_url', 'N/A')}")
                lines.append(f"- **Entregable:** `{p.get('deliverable_path', 'N/A')}`")
                lines.append(f"- **Resumen:** {p.get('summary', '')[:300]}\n")

        lines.append("## ✅ Historial Reciente")
        if not recent_done:
            lines.append("_Sin historial reciente._")
        else:
            for d in reversed(recent_done):
                lines.append(f"- **`{d.get('status', '').upper()}`** — {d.get('title')} (`{d.get('reward_display', '')}`)")

        OBS_REVIEW_MD.parent.mkdir(parents=True, exist_ok=True)
        OBS_REVIEW_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def save_reviews(items: List[Dict[str, Any]]):
    with _review_lock:
        _atomic_write_json(REVIEW_FILE, items)
        _sync_obsidian_markdown(items)


def push_for_review(
    category: str,
    title: str,
    source_url: str,
    reward_display: str,
    estimated_usd: float,
    summary: str,
    deliverable_path: str = "",
    preview_url: str = "",
    solver: str = "DeepSeek API",
    opp_id: str = "",
    action_payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Registra un trabajo terminado y listo para revisión móvil en Discord."""
    items = load_reviews()
    for it in items:
        if opp_id and it.get("opp_id") == opp_id and it.get("status") in ("pending_review", "approved", "sent"):
            return it
        if not opp_id and source_url and it.get("source_url") == source_url and it.get("title") == title and it.get("status") == "pending_review":
            return it

    rev_id = f"rev_{int(time.time())}_{abs(hash(title + source_url)) % 1000}"
    item = {
        "id": rev_id,
        "opp_id": opp_id,
        "category": category,  # github_bounty | apify_actor | poidh_claim
        "title": title,
        "source_url": source_url,
        "reward_display": reward_display,
        "estimated_usd": round(float(estimated_usd), 2),
        "summary": summary[:1200],
        "deliverable_path": deliverable_path,
        "preview_url": preview_url,
        "solver": solver,
        "action_payload": action_payload or {},
        "status": "pending_review",
        "notified_discord": False,
        "feedback": "",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    items.append(item)
    save_reviews(items)
    return item


def get_pending_reviews() -> List[Dict[str, Any]]:
    return [x for x in load_reviews() if x.get("status") == "pending_review"]


def get_unnotified_reviews() -> List[Dict[str, Any]]:
    return [x for x in load_reviews() if x.get("status") == "pending_review" and not x.get("notified_discord")]


def mark_review_notified(rev_id: str):
    items = load_reviews()
    for it in items:
        if it.get("id") == rev_id:
            it["notified_discord"] = True
            break
    save_reviews(items)


def get_review_by_id(rev_id: str) -> Optional[Dict[str, Any]]:
    for it in load_reviews():
        if it.get("id") == rev_id:
            return it
    return None


def update_review_decision(rev_id: str, new_status: str, feedback: str = "", result_note: str = "") -> Optional[Dict[str, Any]]:
    items = load_reviews()
    updated = None
    for it in items:
        if it.get("id") == rev_id:
            it["status"] = new_status
            it["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            if feedback:
                it["feedback"] = feedback
            if result_note:
                it["result_note"] = result_note
            updated = dict(it)
            break
    if updated:
        save_reviews(items)
    return updated
