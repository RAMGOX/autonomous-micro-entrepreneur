"""
Autonomous Daemon: Motor autónomo continuo 24/7 con bucles concurrentes desacoplados.
Ejecuta de forma independiente y aislada:
1. Atención inmediata de órdenes de Discord (cada 5s)
2. Ejecución de tareas con Cerebro 3 (DeepSeek API) estrictamente cada 5 min (300s)
3. Rastreo de micro-recompensas con Cerebro 1 (cada 3 min)
4. Pipeline continuo de investigación y registro on-chain en Base Sepolia
5. Minería de subvenciones y grants (cada 30 min)
"""
import os
import sys
import time
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

from continuous_worker import run_continuous_cycle
from discord_bridge import pop_pending_orders, complete_order, notify_user_discord
from brain_router import route_task
from bounty_hunter import scan_onchain_bounties
from deepseek_solver import run_deepseek_cycle
from poidh_claim_submitter import check_and_notify_pending_claims
from poidh_claim_tracker import check_active_claims_status
from data_curator import process_and_save_intel

async def loop_orders():
    """Atiende órdenes del usuario desde Discord en tiempo real"""
    while True:
        try:
            pending = pop_pending_orders()
            for o in pending:
                order_id = o.get("id")
                text = o.get("text", "")
                log_event(f"[Orders] Procesando orden {order_id}: {text}")
                ans = route_task(
                    task_type="general",
                    prompt=text,
                    difficulty=4,
                    system_prompt="Eres el Cerebro Central del sistema 24/7. Responde de forma técnica y directa."
                )
                response = ans.get("response", "Orden procesada.")
                brain_name = ans.get("brain", "Cerebro Central")
                notify_user_discord(f"**Cerebro:** `{brain_name}`\n\n{response}", title=f"✅ Orden Ejecutada: {text[:40]}...")
                complete_order(order_id, response)
                log_event(f"[Orders] Orden {order_id} completada.")
        except Exception as e:
            log_event(f"[Orders Error]: {e}")
        await asyncio.sleep(5)

async def loop_deepseek():
    """Ejecutor autónomo cada 6 minutos (360s) de Cerebro 3 (DeepSeek API) para tareas on-chain"""
    await asyncio.sleep(15)
    while True:
        try:
            log_event("[DeepSeek Loop] Verificando tareas on-chain pendientes (media/baja)...")
            res = await asyncio.to_thread(run_deepseek_cycle)
            if res:
                log_event("[DeepSeek Loop] Tarea on-chain resuelta con éxito. Solución lista para reclamación.")
            else:
                log_event("[DeepSeek Loop] Sin tareas pendientes o límite de presupuesto diario alcanzado.")
        except Exception as e:
            log_event(f"[DeepSeek Loop Error]: {e}")
        await asyncio.sleep(360)

async def loop_bounties():
    """Rastreador de recompensas on-chain verificadas (POIDH / Base / Arbitrum) cada 3 minutos"""
    await asyncio.sleep(10)
    while True:
        try:
            log_event("[On-Chain Scanner] Rastreador de Smart Contracts escaneando...")
            await asyncio.to_thread(scan_onchain_bounties)
        except Exception as e:
            log_event(f"[On-Chain Scanner Error]: {e}")
        await asyncio.sleep(180)

async def loop_continuous_web3():
    """Pipeline continuo de investigación Web3 y micro-tareas on-chain"""
    await asyncio.sleep(5)
    while True:
        try:
            log_event("[Web3 Pipeline] Ejecutando paso de investigación on-chain...")
            await run_continuous_cycle()
        except Exception as e:
            log_event(f"[Web3 Pipeline Error]: {e}")
        await asyncio.sleep(30)

async def loop_data_curator():
    """Minería y actualización de Grants e inteligencia Web3 cada 30 minutos"""
    await asyncio.sleep(60)
    while True:
        try:
            log_event("[Data Curator Loop] Actualizando Grants e Inteligencia Web3...")
            await asyncio.to_thread(process_and_save_intel)
        except Exception as e:
            log_event(f"[Data Curator Loop Error]: {e}")
        await asyncio.sleep(1800)

async def loop_claim_notifier():
    """Vigila la cola, emite reclamos automáticos on-chain y rastrea pagos aprobados"""
    await asyncio.sleep(5)
    cycle = 0
    while True:
        try:
            await asyncio.to_thread(check_and_notify_pending_claims)
            cycle += 1
            # Cada 4 ciclos (~60s), auditar si algun reclamo fue aprobado on-chain
            if cycle % 4 == 0:
                await asyncio.to_thread(check_active_claims_status)
        except Exception as e:
            log_event(f"[Claim Notifier Error]: {e}")
        await asyncio.sleep(15)

async def main():
    log_event("=" * 65)
    log_event("  AUTONOMOUS MICRO-ENTREPRENEUR - MOTOR ON-CHAIN 24/7")
    log_event("  DeepSeek: Cada 6 min | Scanner: Cada 3 min | Notificador Claims: Cada 15s")
    log_event("=" * 65)
    
    await asyncio.gather(
        loop_orders(),
        loop_deepseek(),
        loop_bounties(),
        loop_continuous_web3(),
        loop_data_curator(),
        loop_claim_notifier()
    )

if __name__ == "__main__":
    asyncio.run(main())
