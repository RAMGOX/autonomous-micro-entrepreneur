"""
System Watchdog: Supervisor local de ultra-baja latencia y auto-recuperacion.
Monitoriza en bucle continuo (cada 5 segundos) los 4 pilares:
1. Ollama local (GTX 1660 en puerto 11434)
2. Servidor Dashboard (puerto 8080)
3. Bot de Discord (mando a distancia 24/7)
4. Daemon autonomo continuo (mineria Web3 y Base Sepolia)

Si cualquiera de los servicios cae o se congela, lo resucita de inmediato en < 2 segundos.
"""
import os
import sys
import time
import json
import urllib.request
import subprocess
import ctypes
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))
PYTHON_EXE = str(BASE_DIR / ".venv" / "Scripts" / "python.exe")
STATE_DIR = BASE_DIR / "memoria" / "estado"
HEALTH_FILE = STATE_DIR / "sistema_salud.json"
QUEUE_FILE = STATE_DIR / "cola_oportunidades.json"
BOT_WALLET = "0x02c1F87F514493F359Afc0B3ff6b587434770361"
BASE_RPC_URL = "https://mainnet.base.org"

try:
    from discord_bridge import notify_user_discord
except Exception:
    notify_user_discord = None

# Blindaje de Instancia Unica para el Watchdog
try:
    kernel32 = ctypes.windll.kernel32
    _watchdog_mutex = kernel32.CreateMutexW(None, True, "Global\\AutonomousMicroEntrepreneur_Watchdog_SingleInstance")
    if kernel32.GetLastError() == 183:
        print("[Watchdog] Ya hay una instancia del supervisor en ejecucion. Saliendo.")
        sys.exit(0)
except Exception:
    pass

def check_http_port(url: str, timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Watchdog/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status in (200, 204)
    except Exception:
        return False

def check_process_running(script_name: str) -> bool:
    try:
        import psutil
        for p in psutil.process_iter(['name', 'cmdline']):
            cmdline = " ".join(p.info.get('cmdline') or [])
            if script_name in cmdline and p.pid != os.getpid():
                return True
        return False
    except Exception:
        return False

def restart_service(name: str, launch_func):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [ALERT] {name} no responde. Reiniciando...")
    try:
        launch_func()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [OK] {name} reiniciado con exito.")
    except Exception as e:
        print(f"[Watchdog Error] No se pudo reiniciar {name}: {e}")

def launch_ollama():
    ollama_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama app.exe")
    if os.path.exists(ollama_path):
        subprocess.Popen([ollama_path], creationflags=subprocess.DETACHED_PROCESS)

def launch_dashboard():
    script = str(BASE_DIR / "src" / "dashboard_server.py")
    subprocess.Popen([PYTHON_EXE, script], cwd=str(BASE_DIR), creationflags=subprocess.CREATE_NO_WINDOW)

def launch_discord():
    script = str(BASE_DIR / "src" / "discord_bot.py")
    subprocess.Popen([PYTHON_EXE, script], cwd=str(BASE_DIR), creationflags=subprocess.CREATE_NO_WINDOW)

def launch_daemon():
    script = str(BASE_DIR / "scripts_generados" / "autonomous_daemon.py")
    subprocess.Popen([PYTHON_EXE, script], cwd=str(BASE_DIR), creationflags=subprocess.CREATE_NO_WINDOW)

def get_base_gas_eth(wallet: str) -> float:
    try:
        data = json.dumps({"jsonrpc": "2.0", "method": "eth_getBalance", "params": [wallet, "latest"], "id": 1}).encode("utf-8")
        req = urllib.request.Request(BASE_RPC_URL, data=data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            res_json = json.loads(res.read())
            wei = int(res_json.get("result", "0x0"), 16)
            return round(wei / 1e18, 6)
    except Exception:
        return 0.0

def get_active_claims_count() -> int:
    try:
        if QUEUE_FILE.exists():
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
                return sum(1 for it in items if it.get("status") == "claimed_onchain")
    except Exception:
        pass
    return 0

def main():
    print("=" * 60)
    print("  AUTONOMOUS SYSTEM WATCHDOG - SUPERVISOR DE ALTA RESILIENCIA")
    print("  Monitoriza: Ollama (11434), Dashboard (8080), Discord & Daemon")
    print("  Frecuencia de muestreo: Cada 5 segundos")
    print("=" * 60)
    
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    
    tick = 0
    cached_gas = get_base_gas_eth(BOT_WALLET)
    cached_claims = get_active_claims_count()
    gas_alert_sent = False
    
    while True:
        status_report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ollama": False,
            "dashboard": False,
            "discord_bot": False,
            "autonomous_daemon": False,
            "base_gas_eth": cached_gas,
            "active_claims": cached_claims
        }
        
        # Muestreo de gas y claims cada 60 segundos (12 ticks de 5s)
        if tick % 12 == 0:
            cached_gas = get_base_gas_eth(BOT_WALLET)
            cached_claims = get_active_claims_count()
            status_report["base_gas_eth"] = cached_gas
            status_report["active_claims"] = cached_claims
            
            # Alerta de gas bajo
            if cached_gas < 0.00005 and not gas_alert_sent:
                if notify_user_discord:
                    notify_user_discord(
                        f"⚠️ **ALERTA DE GAS CRÍTICO EN BASE MAINNET**\n\n"
                        f"• Cartera del bot: `{BOT_WALLET}`\n"
                        f"• Saldo actual: `{cached_gas:.6f} ETH`\n"
                        f"• Umbral de seguridad: `0.00005 ETH`\n\n"
                        f"Se requiere recarga mínima de gas para seguir firmando reclamos.",
                        title="⛽ Saldo de Gas Bajo",
                        color=0xe67e22,
                        channel="dashboard"
                    )
                gas_alert_sent = True
            elif cached_gas >= 0.00005:
                gas_alert_sent = False
        
        tick += 1
        
        # 1. Comprobar Ollama
        status_report["ollama"] = check_http_port("http://127.0.0.1:11434/api/tags")
        if not status_report["ollama"]:
            restart_service("Ollama (IA Local)", launch_ollama)
            time.sleep(2)
            
        # 2. Comprobar Dashboard
        status_report["dashboard"] = check_http_port("http://127.0.0.1:8080/api/status")
        if not status_report["dashboard"]:
            restart_service("Dashboard Server (8080)", launch_dashboard)
            time.sleep(2)
            
        # 3. Comprobar Discord Bot
        status_report["discord_bot"] = check_process_running("discord_bot.py")
        if not status_report["discord_bot"]:
            restart_service("Discord Bot 24/7", launch_discord)
            time.sleep(2)
            
        # 4. Comprobar Daemon Autonomo
        status_report["autonomous_daemon"] = check_process_running("autonomous_daemon.py")
        if not status_report["autonomous_daemon"]:
            restart_service("Autonomous Daemon", launch_daemon)
            time.sleep(2)
            
        # Guardar telemetria de salud
        try:
            with open(HEALTH_FILE, "w", encoding="utf-8") as f:
                json.dump(status_report, f, indent=2)
        except Exception:
            pass
            
        time.sleep(5)

if __name__ == "__main__":
    main()
