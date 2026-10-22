"""
GitHub Deliverer: Entrega autónoma de soluciones de bounties directamente en GitHub.
Toma las soluciones técnicas generadas en memoria/estrategias/soluciones_propuestas/
y las publica automáticamente como Comentario Oficial de Entrega o Pull Request en el repositorio,
incluyendo la cartera del operador para la liberación de los fondos del escrow.
"""
import os
import sys
import re
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from discord_bridge import notify_user_discord

QUEUE_FILE = BASE_DIR / "memoria" / "estado" / "cola_oportunidades.json"
OPERATOR_WALLET = os.getenv("PUBLIC_ADDRESS_TESTNET", "0x02c1F87F514493F359Afc0B3ff6b587434770361")

def safe_print(text: str):
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    except Exception:
        try:
            print(text.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass

def parse_github_url(url: str):
    """Extrae owner, repo y número de issue desde una URL de GitHub"""
    # Ej: https://github.com/Senthemodder/evm-vault-audit/issues/2
    match = re.search(r"github\.com/([^/]+)/([^/]+)/(?:issues|pull)/([0-9]+)", url)
    if match:
        return match.group(1), match.group(2), match.group(3)
    return None, None, None

def submit_solution_to_github(opp: dict, token: str) -> bool:
    """Envía la solución completa como entrega oficial en el issue de GitHub"""
    opp_id = opp.get("id")
    title = opp.get("title", "")
    url = opp.get("url", "")
    sol_path = opp.get("solution_path")
    val_usd = opp.get("estimated_value_usd", 0.0)

    if not sol_path or not os.path.exists(sol_path):
        safe_print(f"[Deliverer Error] Archivo de solucion no encontrado: {sol_path}")
        return False

    owner, repo, issue_num = parse_github_url(url)
    if not owner or not repo or not issue_num:
        safe_print(f"[Deliverer Warning] URL no es un issue estandar de GitHub: {url}")
        return False

    with open(sol_path, "r", encoding="utf-8") as f:
        sol_content = f.read()

    # Cabecera formal de entrega de bounty
    delivery_body = f"""## 🚀 Autonomous Bounty Solution Submission

**Task:** {title}
**Estimated Reward:** ${val_usd:.2f}
**Recipient Wallet (Base Mainnet / EVM):** `{OPERATOR_WALLET}`

---

{sol_content}

---
*Submitted autonomously by [Autonomous Micro-Entrepreneur](https://github.com). Please release escrow funds or reward to `{OPERATOR_WALLET}`.*
"""

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "AutonomousMicroEntrepreneur-Delivery/1.0"
    }

    # Publicar comentario en el issue
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_num}/comments"
    safe_print(f"[Deliverer] Entregando solucion en {owner}/{repo}#{issue_num}...")

    try:
        r = requests.post(api_url, headers=headers, json={"body": delivery_body}, timeout=15)
        if r.status_code in (200, 201):
            comment_data = r.json()
            comment_url = comment_data.get("html_url", url)
            safe_print(f"[Deliverer] [OK] Solucion entregada con exito: {comment_url}")

            # Actualizar estado en la cola
            update_opportunity_delivered(opp_id, comment_url)
            safe_print(f"[Deliverer] Entrega registrada en cola: {comment_url} - Discord silenciado")
            return True
        else:
            safe_print(f"[Deliverer Error] GitHub API devolvio {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        safe_print(f"[Deliverer Exception]: {e}")
        return False

def update_opportunity_delivered(opp_id: str, delivery_url: str):
    """Marca la oportunidad como entregada en la cola de estado"""
    if not QUEUE_FILE.exists():
        return
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
        for it in items:
            if it.get("id") == opp_id:
                it["status"] = "delivered"
                it["delivery_url"] = delivery_url
                it["delivered_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                break
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except Exception as e:
        safe_print(f"[Deliverer Error updating queue]: {e}")

def deliver_all_pending():
    """Revisa cola_oportunidades.json y entrega todas las tareas resueltas no entregadas"""
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    token = os.getenv("GITHUB_TOKEN")

    if not token or token.strip() in ("", "TU_GITHUB_TOKEN_AQUI"):
        safe_print("\n[Deliverer] ALERTA: No hay GITHUB_TOKEN configurado en config/.env")
        safe_print("Para entregar automaticamente las soluciones y cobrar, configura tu token de GitHub.")
        return 0

    if not QUEUE_FILE.exists():
        safe_print("[Deliverer] No hay cola de oportunidades.")
        return 0

    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        return 0

    pending_delivery = [
        it for it in items
        if it.get("status") == "executed" and not it.get("delivery_url")
    ]

    if not pending_delivery:
        safe_print("[Deliverer] No hay soluciones resueltas pendientes de entrega.")
        return 0

    safe_print(f"\n[Deliverer] Detectadas {len(pending_delivery)} solucion(es) listas para entrega en GitHub...")
    delivered_count = 0

    for opp in pending_delivery:
        if submit_solution_to_github(opp, token):
            delivered_count += 1
            time.sleep(2) # Respetar rate limit

    safe_print(f"[Deliverer] Finalizado: {delivered_count}/{len(pending_delivery)} soluciones entregadas.")
    return delivered_count

if __name__ == "__main__":
    deliver_all_pending()
