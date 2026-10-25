"""
Autonomous Daemon v3.0: Motor autónomo continuo 24/7 con bucles concurrentes desacoplados.
- Cero bucles en Base Sepolia y cero gasto de GPU en segundo plano.
- Límite estricto de DeepSeek: 0.50 €/día gestionado atómicamente en brain_router.py.
- Todo trabajo resuelto va a bandeja_revision.json para aprobación móvil del usuario en Discord.

Bucles activos:
1. Atención inmediata de órdenes de Discord (cada 5s)
2. Escáner de Bounties Reales: GitHub/Algora ($25-$3,000 USD) + POIDH Técnico Base/Arbitrum (cada 10 min)
3. Ejecutor DeepSeek / Gemini Flash sobre oportunidades rentables (cada 6 min)
4. Salud y Smoke-Test de Actores Apify / MCP (al arrancar y cada 6 horas)
5. Vigilancia de cobros POIDH y Auto-Sweep USDC/ETH a Coinbase (cada 60s)
"""
import os
import sys
import asyncio
import ctypes
import logging
from pathlib import Path

# Blindaje de Instancia Única para el Daemon
_daemon_mutex = None
try:
    kernel32 = ctypes.windll.kernel32
    _daemon_mutex = kernel32.CreateMutexW(None, True, "Global\\AutonomousMicroEntrepreneur_Daemon_SingleInstance")
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        print("[Autonomous Daemon] Ya hay una instancia del daemon ejecutándose. Saliendo.")
        sys.exit(0)
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))
sys.path.append(str(BASE_DIR / "scripts_generados"))

LOG_FILE = BASE_DIR / "logs" / "autonomous_daemon.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def log_event(msg: str):
    print(msg)
    try:
        logging.info(msg)
    except Exception:
        pass


from discord_bridge import pop_pending_orders, complete_order, notify_user_discord
from brain_router import route_task
from bounty_hunter import scan_onchain_bounties
from deepseek_solver import run_deepseek_cycle
from apify_actor_factory import run_actor_health_checks
from poidh_claim_submitter import check_and_notify_pending_claims
from poidh_claim_tracker import check_active_claims_status


async def loop_orders():
    """Atiende órdenes del usuario enviadas a la cola desde Discord en tiempo real."""
    while True:
        try:
            pending = pop_pending_orders()
            for o in pending:
                order_id = o.get("id")
                text = o.get("text", "")
                log_event(f"[Orders] Procesando orden {order_id}: {text}")
                ans = await asyncio.to_thread(
                    route_task,
                    "general",
                    text,
                    4,
                    "Eres el Cerebro Central de AME v3.0. Responde en español claro, directo y accionable."
                )
                response = ans.get("response", "Orden procesada.")
                brain_name = ans.get("brain", "Cerebro Central")
                notify_user_discord(
                    f"**Motor:** `{brain_name}`\n\n{response[:3800]}",
                    title=f"✅ Orden Ejecutada: {text[:45]}"
                )
                complete_order(order_id, response)
                log_event(f"[Orders] Orden {order_id} completada con {brain_name}.")
        except Exception as e:
            log_event(f"[Orders Error]: {e}")
        await asyncio.sleep(5)


async def loop_bounties():
    """Rastrea bounties técnicos reales en GitHub/Algora y POIDH cada 10 minutos."""
    await asyncio.sleep(8)
    while True:
        try:
            log_event("[Motor 1 Scanner] Buscando bounties reales en GitHub/Algora y POIDH...")
            added = await asyncio.to_thread(scan_onchain_bounties)
            log_event(f"[Motor 1 Scanner] Ciclo completado ({added} nuevas oportunidades en cola).")
        except Exception as e:
            log_event(f"[Motor 1 Scanner Error]: {e}")
        await asyncio.sleep(600)


async def loop_deepseek():
    """Resuelve tareas rentables cada 6 min respetando el tope diario de 0.50 € y envía a Revisión Móvil."""
    await asyncio.sleep(20)
    while True:
        try:
            log_event("[Solver Loop] Evaluando cola de oportunidades con presupuesto <= 0.50 €/día...")
            res = await asyncio.to_thread(run_deepseek_cycle)
            if res:
                log_event("[Solver Loop] Propuesta generada y enviada a Bandeja de Revisión Móvil.")
            else:
                log_event("[Solver Loop] Sin tareas pendientes viables o tope diario alcanzado.")
        except Exception as e:
            log_event(f"[Solver Loop Error]: {e}")
        await asyncio.sleep(360)


async def loop_apify_factory():
    """Verifica y mantiene operativos los Actores Apify / MCP cada 6 horas."""
    await asyncio.sleep(12)
    while True:
        try:
            log_event("[Motor 2 Apify] Ejecutando smoke-test de actores comerciales...")
            results = await asyncio.to_thread(run_actor_health_checks)
            ok_cnt = len([r for r in results if r.get("smoke_ok")])
            log_event(f"[Motor 2 Apify] {ok_cnt}/{len(results)} actores operativos.")
        except Exception as e:
            log_event(f"[Motor 2 Apify Error]: {e}")
        await asyncio.sleep(21600)


async def loop_claim_tracker():
    """Vigila pagos aprobados en Base Mainnet y ejecuta Auto-Sweep de USDC/ETH hacia Coinbase."""
    await asyncio.sleep(15)
    while True:
        try:
            await asyncio.to_thread(check_and_notify_pending_claims)
            await asyncio.to_thread(check_active_claims_status)
        except Exception as e:
            log_event(f"[Claim Tracker Error]: {e}")
        await asyncio.sleep(60)


async def main():
    log_event("=" * 68)
    log_event("  AUTONOMOUS MICRO-ENTREPRENEUR v3.0 — MOTOR 24/7 EN VIVO")
    log_event("  Motores: GitHub Bounties + Apify/MCP + x402 | Tope IA: 0.50 €/día")
    log_event("=" * 68)

    await asyncio.gather(
        loop_orders(),
        loop_bounties(),
        loop_deepseek(),
        loop_apify_factory(),
        loop_claim_tracker()
    )


if __name__ == "__main__":
    asyncio.run(main())
