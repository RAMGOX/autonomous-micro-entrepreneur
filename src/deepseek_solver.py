"""
DeepSeek Solver: Ejecutor autónomo de nivel Medio y Bajo cada 5 minutos.
Consume oportunidades de cola_oportunidades.json clasificadas como 'media' o 'baja',
resuelve el código con DeepSeek API protegiendo el tope de 0.50€/día,
guarda la solución en disco y notifica a Discord.
"""
import os
import sys
import time
import json
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

def safe_print(text: str):
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    except Exception:
        try:
            print(text.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass

ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from opportunity_queue import (
    get_best_pending_opportunity,
    get_top_pending_opportunities,
    mark_opportunity_in_progress,
    mark_opportunity_executed,
    prune_expired_opportunities
)
from discord_bridge import notify_user_discord

DAILY_BUDGET_EUR = float(os.getenv("DEEPSEEK_DAILY_BUDGET_EUR", "0.50"))
BUDGET_STATE_FILE = BASE_DIR / "memoria" / "estado" / "deepseek_presupuesto.json"
SOLUTIONS_DIR = BASE_DIR / "memoria" / "estrategias" / "soluciones_propuestas"

def get_today_spent() -> float:
    today = time.strftime("%Y-%m-%d")
    if BUDGET_STATE_FILE.exists():
        try:
            with open(BUDGET_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == today:
                    return float(data.get("spent_eur", 0.0))
        except Exception:
            pass
    return 0.0

def record_spending(cost_eur: float):
    today = time.strftime("%Y-%m-%d")
    spent = get_today_spent() + cost_eur
    BUDGET_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BUDGET_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "date": today,
            "spent_eur": round(spent, 4),
            "daily_limit_eur": DAILY_BUDGET_EUR,
            "remaining_eur": round(max(0.0, DAILY_BUDGET_EUR - spent), 4),
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }, f, indent=2)

def run_deepseek_cycle():
    """Ejecuta una oportunidad de nivel 'baja' o 'media' si hay presupuesto"""
    prune_expired_opportunities()
    spent = get_today_spent()
    if spent >= DAILY_BUDGET_EUR:
        safe_print(f"[DeepSeek Worker] Límite diario alcanzado ({spent:.4f}€ / {DAILY_BUDGET_EUR:.2f}€). En espera.")
        return False

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        safe_print("[DeepSeek Worker] No hay DEEPSEEK_API_KEY configurada.")
        return False

    # 1. Obtener y bloquear atomicamente la mejor tarea pendiente de nivel 'baja' o 'media'
    opps = get_top_pending_opportunities(["baja", "media"], limit=1, lock=True, solver="DeepSeek API")
    if not opps:
        safe_print("[DeepSeek Worker] No hay tareas pendientes de nivel baja o media.")
        return False

    opp = opps[0]
    opp_id = opp["id"]
    title = opp["title"]
    url = opp["url"]
    desc = opp.get("description", "")
    diff = opp.get("difficulty", "media")
    est_val = opp.get("estimated_value_usd", 0.0)

    safe_print(f"\n[DeepSeek Worker] Bloqueada y tomando tarea [{diff.upper()} | ${est_val}]: {title}")

    prompt = f"""Eres un Ingeniero de Software Senior Autónomo resolviendo una recompensa en GitHub.
Título: {title}
Enlace: {url}
Requerimientos:
{desc}

Genera la solución técnica completa:
1. Código de implementación listo para producción, limpio y autocontenido.
2. Suite mínima de tests unitarios verificando la funcionalidad.
3. Mensaje formal de Pull Request listo para enviar al repositorio.
Incluye la cartera del operador: 0x02c1F87F514493F359Afc0B3ff6b587434770361.
"""

    try:
        import litellm
        messages = [
            {"role": "system", "content": "Eres el Ingeniero de Código Autónomo del sistema. Produce código ejecutable y verificable."},
            {"role": "user", "content": prompt}
        ]

        response = litellm.completion(
            model="deepseek/deepseek-chat",
            messages=messages,
            api_key=api_key
        )
        content = response.choices[0].message.content
        cost = response._hidden_params.get("response_cost", 0.002)
        record_spending(cost)

        # Guardar solución en archivo
        SOLUTIONS_DIR.mkdir(parents=True, exist_ok=True)
        sol_filename = f"solucion_{diff}_{opp_id}.md"
        sol_path = SOLUTIONS_DIR / sol_filename
        with open(sol_path, "w", encoding="utf-8") as f:
            f.write(f"# Solución para: {title}\n")
            f.write(f"- **URL:** {url}\n")
            f.write(f"- **Nivel:** {diff.upper()} | **Valor Est:** ${est_val}\n")
            f.write(f"- **Generado por:** DeepSeek API (Coste: {cost:.4f}€)\n")
            f.write(f"- **Cartera Operador:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`\n\n---\n\n")
            f.write(content)

        mark_opportunity_executed(opp_id, "DeepSeek API", str(sol_path))
        safe_print(f"[DeepSeek Worker] [OK] Solucion generada en: {sol_path} (Coste: {cost:.4f} EUR) - Discord silenciado")
        return True
    except Exception as e:
        safe_print(f"[DeepSeek Worker Error]: {e}")
        return False

if __name__ == "__main__":
    run_deepseek_cycle()
