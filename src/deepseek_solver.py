"""
DeepSeek Solver: Prepara soluciones técnicas completas respetando el tope estricto de 0.50 EUR/día
y las envía a la Bandeja de Revisión Móvil (Discord) para que el usuario las apruebe en 1 toque.
"""
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))
load_dotenv(dotenv_path=BASE_DIR / "config" / ".env")

from brain_router import (
    get_today_spent,
    DAILY_BUDGET_EUR,
    query_deepseek
)
from opportunity_queue import (
    get_best_cost_benefit_opportunity,
    mark_opportunity_executed,
    update_opportunity_status,
    prune_expired_opportunities
)
from review_queue import push_for_review

SOLUTIONS_DIR = BASE_DIR / "memoria" / "estrategias" / "soluciones_propuestas"


def safe_print(text: str):
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    except Exception:
        pass


def run_deepseek_cycle() -> bool:
    prune_expired_opportunities()
    spent = get_today_spent()
    if spent >= DAILY_BUDGET_EUR:
        safe_print(f"[DeepSeek Worker] Tope diario alcanzado ({spent:.4f}€ / {DAILY_BUDGET_EUR:.2f}€). En espera.")
        return False

    if not os.getenv("DEEPSEEK_API_KEY"):
        return False

    opp = get_best_cost_benefit_opportunity(["media", "baja"], lock=True, solver="DeepSeek V3")
    if not opp:
        safe_print("[DeepSeek Worker] Sin tareas nuevas rentables en cola (0.00€ gastados).")
        return False

    opp_id = opp["id"]
    source = opp.get("source", "other")
    title = opp.get("title", "Sin título")
    url = opp.get("url", "")
    desc = opp.get("description", "")
    diff = opp.get("difficulty", "media")
    est_val = float(opp.get("estimated_value_usd", 0.0))
    rew_curr = opp.get("reward_currency", f"${est_val}")

    prompt = f"""Analiza y prepara la solución técnica completa para esta oportunidad remunerada ({source.upper()}).
Título: {title}
URL: {url}
Recompensa: {rew_curr} (~${est_val} USD)
Descripción:
{desc}

Reglas estrictas:
1. Si la tarea NO se puede resolver 100% con código/datos desde un PC (ej. exige foto física, comprar tokens, publicar desde cuenta verificada ajena o vídeo real), responde en la primera línea exactamente: DESCARTAR_NO_VIABLE y explica en 1 frase por qué.
2. Si ES viable por software:
   - Escribe primero un bloque '## Resumen Ejecutivo para Revisión Móvil' (máximo 5 líneas claras explicando qué hace la solución y cómo verificarla).
   - Después escribe el código completo, limpio, sin placeholders, listo para probar y entregar.
   - Incluye al final un comando o test rápido de verificación local.
"""

    try:
        ds_res = query_deepseek(
            prompt=prompt,
            system="Eres un Ingeniero de Software Senior pragmático. Cero relleno. Código limpio y verificable.",
            reasoner=False
        )
        if not ds_res:
            update_opportunity_status(opp_id, "pending")
            return False

        content = ds_res["response"]
        cost_eur = ds_res["cost"]

        if "DESCARTAR_NO_VIABLE" in content[:120] or any(
            k in content.lower()[:300] for k in ["no es resoluble por código", "no es resoluble por software", "prueba física"]
        ):
            safe_print(f"[DeepSeek Worker] Descartada por no ser viable en software puro: {title}")
            update_opportunity_status(opp_id, "discarded_unsolvable")
            return False

        SOLUTIONS_DIR.mkdir(parents=True, exist_ok=True)
        sol_path = SOLUTIONS_DIR / f"solucion_{diff}_{opp_id}.md"
        sol_path.write_text(
            f"# Propuesta Técnica: {title}\n"
            f"- **Origen:** {url}\n"
            f"- **Recompensa:** `{rew_curr}` (~`${est_val} USD`)\n"
            f"- **Motor:** {ds_res['brain']} (`{cost_eur:.4f} €`)\n\n---\n\n{content}\n",
            encoding="utf-8"
        )

        # Extraer breve resumen para Discord móvil
        summary_lines = [ln.strip() for ln in content.splitlines() if ln.strip() and not ln.startswith("#")][:5]
        short_summary = "\n".join(summary_lines)[:500]

        category = "github_bounty" if source == "github_bounty" else "poidh_claim"
        mark_opportunity_executed(opp_id, ds_res["brain"], str(sol_path))

        push_for_review(
            category=category,
            title=title,
            source_url=url,
            reward_display=f"{rew_curr} (~${est_val:.0f})",
            estimated_usd=est_val,
            summary=short_summary,
            deliverable_path=str(sol_path.relative_to(BASE_DIR)),
            solver=ds_res["brain"],
            opp_id=opp_id,
            action_payload={
                "source": source,
                "url": url,
                "solution_path": str(sol_path)
            }
        )
        safe_print(f"[DeepSeek Worker] Lista para revisión móvil en Discord: {title} (Coste: {cost_eur:.4f}€)")
        return True
    except Exception as e:
        safe_print(f"[DeepSeek Worker Error]: {e}")
        update_opportunity_status(opp_id, "pending")
        return False


if __name__ == "__main__":
    run_deepseek_cycle()
