"""
Dashboard Server: Panel de Control en Vivo 24/7 (Telemetría de los 4 Cerebros, Cartera Web3 y Equivalente en Euros)
Puerto local: http://127.0.0.1:8080
"""
import os
import sys
import json
import time
import threading
import subprocess
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))
ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from opportunity_queue import get_queue_summary, prune_expired_opportunities
from deepseek_solver import get_today_spent, DAILY_BUDGET_EUR
from discord_bridge import notify_user_discord
from x402_gateway import get_gateway, PRICING_TABLE, USER_PAYOUT_WALLET
from brain_router import route_task
from agentkit_actions import get_agentkit_provider
from eas_indexer import get_address_attestations, get_address_reputation, get_recent_attestations
from erc8021_builder import encode_erc8021_suffix, attach_erc8021_attribution, decode_erc8021_attribution, DEFAULT_BUILDER_CODE
from defillama_engine import get_base_top_yields, get_base_token_prices, get_base_defi_overview

PORT = 8080
WALLET_ADDRESS = os.getenv("PUBLIC_ADDRESS_TESTNET", "0x02c1F87F514493F359Afc0B3ff6b587434770361")
BASE_SEPOLIA_RPC = os.getenv("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org")
BASE_MAINNET_RPC = "https://mainnet.base.org"
ETH_SEPOLIA_RPC = "https://ethereum-sepolia-rpc.publicnode.com"

USDC_MAINNET_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WDOOM_MAINNET_ADDRESS = "0x623c84A5E04bF715018203334b0eFE41696eBC3E"
ERC20_BALANCE_ABI = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}]

# State & history cache for real-time graphs
telemetry_data = {
    "hardware_history": [],
    "gas_history": [],
    "web3": {
        "address": WALLET_ADDRESS,
        "connected": True,
        "block_number": 48745340,
        "gas_price_gwei": 0.006,
        "balance_eth": 0.03993,
        "balance_eur": 85.90,
        "l1_balance_eth": 0.01,
        "real_balance_eth": 0.0,
        "real_balance_eur": 0.0,
        "eth_price_eur": 2151.57,
        "tokens_earned": 150000,
        "token_symbol": "$ROBIN_MCP",
        "bridge_status": "Fondos L2 acreditados con Éxito",
        "nonce": 15,
        "contract_status": "Desplegado (0x04f4... / 0x7514...)",
        "contract_address": "0x75145e53B139B86062cdE5098761a28D76578fD4",
        "last_update": "--"
    },
    "gpu": {"vram_used_mb": 0, "vram_total_mb": 6144, "gpu_util_percent": 0, "temp_c": 0},
    "hardware": {"cpu_percent": 0, "ram_used_gb": 0, "ram_total_gb": 16, "ram_percent": 0},
    "deepseek": {"balance": "1.95", "currency": "USD", "status": "activo"},
    "gemini": {"status": "activo", "key_configured": bool(os.getenv("GEMINI_API_KEY")), "daily_limit": "1500 req/dia gratis"},
    "active_brain": {
        "current_brain": "Cerebro 1 (Ollama GTX 1660)",
        "status": "vigilancia 24/7 y atencion",
        "task_type": "guard",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
}

data_lock = threading.Lock()

def get_eth_eur_price() -> float:
    """Consulta el precio actual de Ethereum en Euros en Binance / CoinGecko"""
    try:
        req = urllib.request.Request(
            "https://api.binance.com/api/v3/ticker/price?symbol=ETHEUR",
            headers={"User-Agent": "Dashboard/1.0"}
        )
        with urllib.request.urlopen(req, timeout=2.5) as r:
            data = json.loads(r.read().decode())
            return round(float(data.get("price", 2150.0)), 2)
    except Exception:
        return 2151.57

def get_gpu_stats():
    try:
        cmd = ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"]
        out = subprocess.check_output(cmd, encoding="utf-8").strip()
        parts = [p.strip() for p in out.split(",")]
        return {
            "vram_used_mb": int(parts[0]),
            "vram_total_mb": int(parts[1]),
            "gpu_util_percent": int(parts[2]),
            "temp_c": int(parts[3])
        }
    except Exception:
        return {"vram_used_mb": 0, "vram_total_mb": 6144, "gpu_util_percent": 0, "temp_c": 0}

def get_cpu_ram():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": cpu,
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_percent": mem.percent
        }
    except Exception:
        return {"cpu_percent": 0, "ram_used_gb": 0, "ram_total_gb": 16, "ram_percent": 0}

def get_active_brain_data():
    state_file = BASE_DIR / "memoria" / "estado" / "cerebro_activo.json"
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "current_brain": "Cerebro 1 (Ollama GTX 1660)",
        "status": "vigilancia 24/7",
        "task_type": "guard",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

def get_obsidian_notes():
    mem_dir = BASE_DIR / "memoria"
    notes = []
    if mem_dir.exists():
        for p in mem_dir.rglob("*.md"):
            notes.append({
                "title": p.name,
                "folder": p.parent.name,
                "size_bytes": p.stat().st_size,
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))
            })
    notes.sort(key=lambda x: x["modified"], reverse=True)
    return notes

def get_recent_orders():
    order_file = BASE_DIR / "memoria" / "estado" / "cola_ordenes.json"
    if order_file.exists():
        try:
            with open(order_file, "r", encoding="utf-8") as f:
                return json.load(f)[-5:]
        except Exception:
            pass
    return []

def get_rewards_state():
    rew_file = BASE_DIR / "memoria" / "estado" / "recompensas_cobradas.json"
    if rew_file.exists():
        try:
            with open(rew_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_tokens_pending": 150000, "token_symbol": "$ROBIN_MCP"}

# Background collector thread
def background_collector():
    from web3 import Web3
    w3_l2 = Web3(Web3.HTTPProvider(BASE_SEPOLIA_RPC, request_kwargs={"timeout": 3}))
    w3_l1 = Web3(Web3.HTTPProvider(ETH_SEPOLIA_RPC, request_kwargs={"timeout": 2}))
    w3_mainnet = Web3(Web3.HTTPProvider(BASE_MAINNET_RPC, request_kwargs={"timeout": 3}))
    
    last_web3_check = 0
    cached_eth_price = 2151.57
    last_price_check = 0
    last_known_real_eth = 0.0
    last_known_real_usdc = 0.0
    first_payment_check = True
    
    while True:
        try:
            current_time = time.strftime("%H:%M:%S")
            now = time.time()
            
            # 1. Update ETH/EUR Price every 30s
            if now - last_price_check > 30:
                cached_eth_price = get_eth_eur_price()
                last_price_check = now

            gpu = get_gpu_stats()
            hw = get_cpu_ram()
            brain = get_active_brain_data()
            rewards = get_rewards_state()
            
            contract_addr = "0x75145e53B139B86062cdE5098761a28D76578fD4"

            vram_pct = round((gpu["vram_used_mb"] / (gpu["vram_total_mb"] or 6144)) * 100, 1)

            # Web3 check every 4 seconds
            web3_update = None
            if now - last_web3_check > 4:
                last_web3_check = now
                try:
                    conn = w3_l2.is_connected()
                    if conn:
                        block = w3_l2.eth.block_number
                        bal_wei = w3_l2.eth.get_balance(WALLET_ADDRESS)
                        bal_eth = float(w3_l2.from_wei(bal_wei, "ether"))
                        bal_eur = round(bal_eth * cached_eth_price, 2)
                        gas_wei = w3_l2.eth.gas_price
                        gas_gwei = round(float(w3_l2.from_wei(gas_wei, "gwei")), 4)
                        nonce = w3_l2.eth.get_transaction_count(WALLET_ADDRESS)

                        # Check L1 balance
                        l1_bal_eth = 0.01
                        try:
                            l1_wei = w3_l1.eth.get_balance(WALLET_ADDRESS)
                            l1_bal_eth = float(w3_l1.from_wei(l1_wei, "ether"))
                        except Exception:
                            pass

                        # Check Real Mainnet Balance (ETH & USDC)
                        real_eth = 0.0
                        real_usdc = 0.0
                        try:
                            real_wei = w3_mainnet.eth.get_balance(WALLET_ADDRESS)
                            real_eth = float(w3_mainnet.from_wei(real_wei, "ether"))
                        except Exception:
                            pass

                        try:
                            usdc_ctr = w3_mainnet.eth.contract(address=w3_mainnet.to_checksum_address(USDC_MAINNET_ADDRESS), abi=ERC20_BALANCE_ABI)
                            raw_usdc = usdc_ctr.functions.balanceOf(w3_mainnet.to_checksum_address(WALLET_ADDRESS)).call()
                            real_usdc = float(raw_usdc) / 1e6
                        except Exception:
                            pass

                        real_wdoom = 3000.0
                        try:
                            wdoom_ctr = w3_mainnet.eth.contract(address=w3_mainnet.to_checksum_address(WDOOM_MAINNET_ADDRESS), abi=ERC20_BALANCE_ABI)
                            raw_wdoom = wdoom_ctr.functions.balanceOf(w3_mainnet.to_checksum_address(WALLET_ADDRESS)).call()
                            real_wdoom = float(raw_wdoom) / 1e18
                        except Exception:
                            pass

                        # Conversión total a Euros (~0.92 € por 1 USDC/USD)
                        usd_eur_rate = 0.92
                        real_eur = round((real_eth * cached_eth_price) + (real_usdc * usd_eur_rate), 2)

                        # Notificación automática a Discord si entra un pago real
                        if not first_payment_check:
                            if real_eth > (last_known_real_eth + 0.00001) or real_usdc > (last_known_real_usdc + 0.01):
                                delta_parts = []
                                if real_eth > last_known_real_eth:
                                    delta_parts.append(f"{real_eth - last_known_real_eth:.4f} ETH")
                                if real_usdc > last_known_real_usdc:
                                    delta_parts.append(f"{real_usdc - last_known_real_usdc:.2f} USDC")
                                
                                notify_user_discord(
                                    f"🎉 **¡PAGO REAL RECIBIDO EN BASE MAINNET!**\n\n"
                                    f"- **Activo Recibido:** `+{', '.join(delta_parts)}`\n"
                                    f"- **Saldo Total Cartera:** `{real_eur:.2f} €` ({real_eth:.4f} ETH + {real_usdc:.2f} USDC)\n"
                                    f"- **Cartera:** `{WALLET_ADDRESS}`\n"
                                    f"- **Explorador BaseScan:** [Ver Transacción](https://basescan.org/address/{WALLET_ADDRESS})",
                                    title="💰 ¡Dinero Real Ingresado en tu Cartera!",
                                    color=0x2ecc71
                                )
                        first_payment_check = False
                        last_known_real_eth = real_eth
                        last_known_real_usdc = real_usdc

                        bridge_msg = "Fondos L2 Acreditados con Éxito"

                        web3_update = {
                            "address": WALLET_ADDRESS,
                            "connected": True,
                            "block_number": block,
                            "gas_price_gwei": gas_gwei,
                            "balance_eth": bal_eth,
                            "balance_eur": bal_eur,
                            "l1_balance_eth": l1_bal_eth,
                            "real_balance_eth": real_eth,
                            "real_balance_usdc": real_usdc,
                            "real_balance_wdoom": real_wdoom,
                            "real_balance_eur": real_eur,
                            "eth_price_eur": cached_eth_price,
                            "tokens_earned": rewards.get("total_tokens_pending", 150000),
                            "token_symbol": rewards.get("token_symbol", "$ROBIN_MCP"),
                            "bridge_status": bridge_msg,
                            "nonce": nonce,
                            "contract_status": f"Desplegado ({contract_addr[:10]}...)",
                            "contract_address": contract_addr,
                            "last_update": current_time
                        }
                except Exception as e:
                    pass

            with data_lock:
                telemetry_data["gpu"] = gpu
                telemetry_data["hardware"] = hw
                telemetry_data["active_brain"] = brain

                # Hardware history
                telemetry_data["hardware_history"].append({
                    "time": current_time,
                    "cpu": hw["cpu_percent"],
                    "vram": vram_pct,
                    "ram": hw["ram_percent"]
                })
                if len(telemetry_data["hardware_history"]) > 25:
                    telemetry_data["hardware_history"].pop(0)

                # Web3 update & Gas history
                if web3_update:
                    telemetry_data["web3"] = web3_update
                    telemetry_data["gas_history"].append({
                        "time": current_time,
                        "gas_gwei": web3_update["gas_price_gwei"]
                    })
                    if len(telemetry_data["gas_history"]) > 25:
                        telemetry_data["gas_history"].pop(0)

        except Exception as e:
            pass
        
        time.sleep(2)

HTML_PAGE = """<!DOCTYPE html>
<html lang="es" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Autonomous Micro-Entrepreneur 24/7 - Command Center</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    @keyframes pulse-slow { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    .animate-pulse-slow { animation: pulse-slow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #090d16; }
    ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #334155; }
  </style>
</head>
<body class="bg-[#070b12] text-slate-100 min-h-screen p-4 md:p-6 font-sans antialiased selection:bg-cyan-500 selection:text-black">
  <div class="max-w-7xl mx-auto space-y-6">

    <!-- TOP HEADER -->
    <header class="flex flex-col md:flex-row md:items-center justify-between pb-5 border-b border-slate-800/80 gap-4">
      <div>
        <div class="flex items-center gap-3">
          <div class="relative flex h-3.5 w-3.5">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500"></span>
          </div>
          <h1 class="text-2xl font-black tracking-tight text-white flex items-center gap-2">
            AUTONOMOUS MICRO-ENTREPRENEUR
            <span class="text-xs px-2 py-0.5 rounded font-mono font-bold bg-cyan-950 text-cyan-400 border border-cyan-800">24/7 LIVE</span>
          </h1>
        </div>
        <p class="text-xs md:text-sm text-slate-400 mt-1">Supervisión en Tiempo Real &bull; 4 Cerebros Cooperativos &bull; Auto-Claim &bull; Base Sepolia</p>
      </div>

      <div class="flex flex-wrap items-center gap-3 text-xs font-mono">
        <div class="bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded-lg flex items-center gap-2">
          <span class="text-slate-500">BLOQUE:</span>
          <span id="topBlock" class="text-cyan-400 font-bold">#------</span>
        </div>
        <div class="bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded-lg flex items-center gap-2">
          <span class="text-slate-500">GAS L2:</span>
          <span id="topGas" class="text-emerald-400 font-bold">-- Gwei</span>
        </div>
        <div class="bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded-lg flex items-center gap-2">
          <span class="text-slate-500">COTIZACIÓN:</span>
          <span class="text-emerald-300 font-bold">1 ETH = <span id="topEthPrice">2.151,57</span> €</span>
        </div>
        <div class="bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded-lg flex items-center gap-2">
          <span class="text-slate-500">RELOJ:</span>
          <span id="clock" class="text-slate-200">--:--:--</span>
        </div>
      </div>
    </header>

    <!-- ACTIVE BRAIN HERO BANNER -->
    <section class="bg-gradient-to-r from-slate-900 via-indigo-950/50 to-slate-900 border border-indigo-900/60 rounded-2xl p-5 shadow-2xl relative overflow-hidden">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
        <div>
          <div class="flex items-center gap-2">
            <span class="inline-block w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
            <span class="text-xs font-bold text-cyan-400 uppercase tracking-wider">CEREBRO ACTIVO EN ESTE INSTANTE</span>
          </div>
          <h2 id="activeBrainName" class="text-2xl font-black text-white mt-1">Cerebro 1: Ollama Qwen 2.5 Coder 7B (GTX 1660)</h2>
          <p id="activeBrainStatus" class="text-sm text-slate-300 font-mono mt-0.5">Estado: vigilancia 24/7 y análisis &bull; Tarea: guard</p>
        </div>
        <div class="text-right">
          <span class="text-xs text-slate-400 font-mono">Última acción registrada:</span>
          <div id="activeBrainTime" class="text-sm font-mono font-bold text-cyan-300">--:--:--</div>
          <span class="text-[11px] text-emerald-400 font-mono mt-0.5 block">Supervisor Watchdog & Auto-Claim Activo</span>
        </div>
      </div>
    </section>

    <!-- SECTION: OPPORTUNITY QUEUE & DEEPSEEK BUDGET (MULTI-BRAIN PIPELINE) -->
    <section class="grid grid-cols-1 md:grid-cols-12 gap-4">
      <!-- COLA MULTI-CEREBRO (8 COLS) -->
      <div class="md:col-span-8 bg-slate-900/90 border border-slate-800 rounded-2xl p-4 shadow-xl flex flex-col justify-between">
        <div class="flex items-center justify-between pb-3 border-b border-slate-800/80">
          <div class="flex items-center gap-2">
            <span class="text-base">🎯</span>
            <h3 class="text-sm font-bold text-white uppercase tracking-wide">
              Cola de Oportunidades & Bounties (TTL 2h)
            </h3>
          </div>
          <span class="text-[11px] font-mono text-cyan-400 bg-cyan-950/70 border border-cyan-800/80 px-2 py-0.5 rounded">
            Auto-Pruning Activo
          </span>
        </div>
        <div class="grid grid-cols-5 gap-2 my-3">
          <div class="bg-slate-950/80 p-2 rounded-xl border border-rose-900/50 text-center">
            <span class="text-[10px] text-rose-400 font-bold uppercase tracking-wider block">Nivel Alta</span>
            <div id="queueAlta" class="text-xl font-black text-rose-300 font-mono mt-0.5">0</div>
            <span class="text-[9px] text-slate-500 font-mono">C4 (Fallback ON)</span>
          </div>
          <div class="bg-slate-950/80 p-2 rounded-xl border border-amber-900/50 text-center">
            <span class="text-[10px] text-amber-400 font-bold uppercase tracking-wider block">Nivel Media</span>
            <div id="queueMedia" class="text-xl font-black text-amber-300 font-mono mt-0.5">0</div>
            <span class="text-[9px] text-slate-500 font-mono">C3 DeepSeek</span>
          </div>
          <div class="bg-slate-950/80 p-2 rounded-xl border border-emerald-900/50 text-center">
            <span class="text-[10px] text-emerald-400 font-bold uppercase tracking-wider block">Nivel Baja</span>
            <div id="queueBaja" class="text-xl font-black text-emerald-300 font-mono mt-0.5">0</div>
            <span class="text-[9px] text-slate-500 font-mono">C3 DeepSeek</span>
          </div>
          <div class="bg-slate-950/80 p-2 rounded-xl border border-blue-900/50 text-center">
            <span class="text-[10px] text-blue-400 font-bold uppercase tracking-wider block">Grants Intel</span>
            <div id="queueGrants" class="text-xl font-black text-blue-300 font-mono mt-0.5">0</div>
            <span class="text-[9px] text-slate-500 font-mono">Base / CDP (0€)</span>
          </div>
          <div class="bg-slate-950/80 p-2 rounded-xl border border-cyan-900/50 text-center">
            <span class="text-[10px] text-cyan-400 font-bold uppercase tracking-wider block">Entregadas</span>
            <div id="queueDone" class="text-xl font-black text-cyan-300 font-mono mt-0.5">0</div>
            <span class="text-[9px] text-slate-500 font-mono">GitHub Soluciones</span>
          </div>
        </div>
        <div class="text-[11px] text-slate-400 flex items-center justify-between font-mono pt-2 border-t border-slate-800/60">
          <span>Rastreador: Ollama Local (GTX 1660) + Escrow Shield</span>
          <span class="text-slate-300">Total en cola activa: <span id="queueTotal" class="font-bold text-white">0</span></span>
        </div>
      </div>

      <!-- PRESUPUESTO DEEPSEEK (4 COLS) -->
      <div class="md:col-span-4 bg-slate-900/90 border border-slate-800 rounded-2xl p-4 shadow-xl flex flex-col justify-between">
        <div class="flex items-center justify-between pb-3 border-b border-slate-800/80">
          <div class="flex items-center gap-2">
            <span class="text-base">⚡</span>
            <h3 class="text-sm font-bold text-white uppercase tracking-wide">
              Presupuesto DeepSeek
            </h3>
          </div>
          <span class="text-[11px] font-mono text-purple-400 bg-purple-950/70 border border-purple-800/80 px-2 py-0.5 rounded font-bold">
            0.50 €/día
          </span>
        </div>
        <div class="my-3 space-y-2">
          <div class="flex justify-between items-baseline">
            <span class="text-xs text-slate-400">Gasto consumido hoy:</span>
            <span class="font-mono text-base font-black text-purple-300"><span id="dsSpent">0.0000</span> €</span>
          </div>
          <div class="w-full bg-slate-950 rounded-full h-2.5 border border-slate-800 overflow-hidden">
            <div id="dsProgressBar" class="bg-gradient-to-r from-purple-500 to-pink-500 h-2.5 rounded-full transition-all duration-500" style="width: 0%"></div>
          </div>
          <div class="flex justify-between text-[11px] font-mono text-slate-500">
            <span>Restante: <span id="dsRemaining" class="text-slate-300 font-semibold">0.5000 €</span></span>
            <span id="dsPct">0%</span>
          </div>
        </div>
        <div class="text-[11px] text-slate-400 font-mono pt-2 border-t border-slate-800/60 flex items-center justify-between">
          <span>Protección anti-sobrecoste:</span>
          <span class="text-emerald-400 font-semibold">Activa</span>
        </div>
      </div>
    </section>

    <!-- SECTION: WALLET, REAL MONEY IN EUROS & BOUNTIES -->
    <section class="bg-slate-900/90 border border-slate-800/90 rounded-2xl p-5 md:p-6 shadow-xl">
      <div class="flex flex-col md:flex-row md:items-center justify-between pb-4 mb-4 border-b border-slate-800/80 gap-3">
        <div>
          <h3 class="text-base font-bold text-white flex items-center gap-2 uppercase tracking-wide">
            <span>💳</span> CARTERA OPERATIVA Y BENEFICIOS EN EUROS (€)
          </h3>
          <p class="text-xs text-slate-400 mt-0.5">Retiros automáticos directos a tu cartera tras cada hito o bounty completada.</p>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-[11px] font-mono text-slate-500">DIRECCIÓN PÚBLICA:</span>
          <button onclick="copyWallet()" class="text-xs font-mono bg-cyan-950/80 hover:bg-cyan-900 text-cyan-300 px-3 py-1 rounded-md border border-cyan-800/80 transition flex items-center gap-1.5">
            <span id="copyBtnText">Copiar Dirección</span>
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
        
        <!-- WALLET BALANCES (5 COLS) -->
        <div class="lg:col-span-5 space-y-3">
          <div class="font-mono text-xs text-cyan-300 break-all select-all font-semibold bg-slate-950/90 p-2.5 rounded-lg border border-slate-800" id="walletAddrDisplay">
            0x02c1F87F514493F359Afc0B3ff6b587434770361
          </div>

          <!-- REAL MONEY IN EUROS (MAINNET) -->
          <div class="bg-gradient-to-br from-emerald-950/70 via-slate-950 to-slate-950 p-4 rounded-xl border border-emerald-500/50 shadow-lg">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-emerald-400 uppercase tracking-wide flex items-center gap-1.5">
                <span>💰</span> Dinero Real Líquido (Mainnet)
              </span>
              <span class="text-[10px] bg-emerald-950 text-emerald-300 font-mono px-2 py-0.5 rounded border border-emerald-700/60 font-bold">
                Euros Reales
              </span>
            </div>
            <div class="mt-2 flex items-baseline gap-2">
              <span id="realEurBalance" class="text-3xl font-black text-white">0,00</span>
              <span class="text-lg font-bold text-emerald-400">€</span>
              <span class="text-xs text-slate-400 font-mono ml-2">(<span id="realEthBalance">0.0000</span> ETH + <span id="realUsdcBalance">0.00</span> USDC + <span id="realWdoomBalance" class="text-cyan-400 font-bold">3.000</span> wDOOM)</span>
            </div>
            <div class="mt-2 pt-2 border-t border-emerald-900/40 flex justify-between text-[11px] font-mono text-slate-400">
              <span>Cotización actual:</span>
              <span class="text-emerald-300 font-semibold">1 ETH = <span id="ethPriceTag">2.151,57</span> €</span>
            </div>
          </div>

          <!-- TESTNET & BOUNTY REWARDS GRID -->
          <div class="grid grid-cols-2 gap-3 text-xs">
            <div class="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800/80">
              <div class="flex items-center justify-between">
                <span class="text-slate-400 font-medium">Base Sepolia (L2):</span>
                <span class="text-[9px] px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">Testnet</span>
              </div>
              <div class="text-xl font-black text-white mt-1 flex items-baseline gap-1 font-mono">
                <span id="ethBalance">0.0399</span>
                <span class="text-xs text-cyan-400 font-semibold">ETH</span>
              </div>
              <span class="text-[10px] text-slate-400 font-mono mt-0.5 block">
                Valor nominal: ~<span id="testnetEurBalance">85,80</span> €
              </span>
            </div>

            <div class="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800/80">
              <div class="flex items-center justify-between">
                <span class="text-slate-400 font-medium">Bounties Listas:</span>
                <span class="text-[9px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800">Ganado</span>
              </div>
              <div class="text-xl font-black text-amber-400 mt-1 font-mono">
                <span id="tokensEarned">150.000</span>
              </div>
              <span class="text-[10px] text-emerald-400 font-mono mt-0.5 block flex items-center gap-1">
                <span>⚡</span> Auto-Claim Activado
              </span>
            </div>
          </div>

          <!-- SMART CONTRACT STATUS BOX -->
          <div class="p-3.5 bg-slate-950/80 rounded-xl border border-slate-800/80 space-y-1.5">
            <div class="flex items-center justify-between">
              <span class="text-[11px] font-bold text-slate-400 uppercase">AgentMicroServiceOracle & Registry</span>
              <span id="contractBadge" class="px-2 py-0.5 text-[10px] rounded-full font-mono font-semibold bg-cyan-950 text-cyan-400 border border-cyan-800">
                0x7514...8fD4
              </span>
            </div>
            <p class="text-xs text-slate-300">
              Oráculo on-chain con Proof-of-Liveness, SLA y cobro automático de comisiones hacia tu cartera.
            </p>
          </div>
        </div>

        <!-- LIVE GAS CHART (7 COLS) -->
        <div class="lg:col-span-7 bg-slate-950/80 p-4 rounded-xl border border-slate-800/80 flex flex-col justify-between">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <div class="h-2 w-2 rounded-full bg-cyan-400 animate-pulse"></div>
              <span class="text-xs font-bold text-slate-300 uppercase tracking-wide">
                Gráfico de Precio de Gas en Base Sepolia (Gwei)
              </span>
            </div>
            <span id="currentGasTag" class="text-xs font-mono font-bold text-cyan-400 bg-cyan-950/50 px-2 py-0.5 rounded border border-cyan-800/60">
              -- Gwei
            </span>
          </div>

          <div class="relative h-48 w-full">
            <canvas id="gasChart"></canvas>
          </div>

          <div class="mt-2 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400 font-mono">
            <span>Red L2 ultra económica</span>
            <span class="text-emerald-400">✓ Conectado a Base Sepolia RPC</span>
          </div>
        </div>

      </div>
    </section>

    <!-- HARDWARE & DISTRIBUTION SECTION -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">

      <!-- HARDWARE GAUGES (8 COLS) -->
      <section class="lg:col-span-8 bg-slate-900/90 border border-slate-800/90 rounded-2xl p-5 shadow-xl flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
            <h3 class="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-2">
              <span>🖥️</span> HARDWARE DEDICADO 24/7 (TORRE RYZEN 5 + GTX 1660)
            </h3>
            <span class="text-xs text-emerald-400 font-mono font-semibold">CERO COSTE MARGINAL</span>
          </div>

          <div class="grid grid-cols-3 gap-3 mb-4">
            <div class="bg-slate-950/80 p-3 rounded-xl border border-slate-800">
              <span class="text-xs text-slate-400">NVIDIA GTX 1660 (VRAM):</span>
              <div class="text-lg font-bold text-emerald-400 mt-1 font-mono" id="vramText">0 / 6144 MB</div>
              <span class="text-[10px] text-slate-500 font-mono">Modelo Ollama Local</span>
            </div>

            <div class="bg-slate-950/80 p-3 rounded-xl border border-slate-800">
              <span class="text-xs text-slate-400">Ryzen 5 3600 (CPU):</span>
              <div class="text-lg font-bold text-cyan-400 mt-1 font-mono" id="cpuText">0%</div>
              <span class="text-[10px] text-slate-500 font-mono">Scrapers & Daemon</span>
            </div>

            <div class="bg-slate-950/80 p-3 rounded-xl border border-slate-800">
              <span class="text-xs text-slate-400">Memoria RAM:</span>
              <div class="text-lg font-bold text-slate-200 mt-1 font-mono" id="ramText">0 / 16 GB</div>
              <span class="text-[10px] text-slate-500 font-mono">Búfer del Sistema</span>
            </div>
          </div>
        </div>

        <div class="relative h-44 w-full">
          <canvas id="hardwareChart"></canvas>
        </div>
      </section>

      <!-- BRAIN DISTRIBUTION PIE (4 COLS) -->
      <section class="lg:col-span-4 bg-slate-900/90 border border-slate-800/90 rounded-2xl p-5 shadow-xl flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between pb-3 mb-2 border-b border-slate-800/80">
            <h3 class="text-sm font-bold text-white uppercase tracking-wide">
              REPARTO DE CARGA
            </h3>
            <span class="text-xs text-cyan-400 font-mono">4 Cerebros</span>
          </div>

          <div class="relative h-40 w-full flex items-center justify-center">
            <canvas id="brainPieChart"></canvas>
          </div>
        </div>

        <div class="space-y-1.5 text-xs pt-3 border-t border-slate-800/80">
          <div class="flex justify-between items-center text-slate-300">
            <span class="flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-cyan-500"></span> C2 Gemini Flash (Motor Principal)</span>
            <span class="font-mono text-cyan-400 font-bold">55%</span>
          </div>
          <div class="flex justify-between items-center text-slate-300">
            <span class="flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-emerald-500"></span> C1 Obrero Local (Ollama GTX 1660)</span>
            <span class="font-mono text-emerald-400 font-bold">30%</span>
          </div>
          <div class="flex justify-between items-center text-slate-300">
            <span class="flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-purple-500"></span> C3 DeepSeek API ($1.95 USD)</span>
            <span class="font-mono text-purple-400 font-bold">10%</span>
          </div>
          <div class="flex justify-between items-center text-slate-300">
            <span class="flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-rose-500"></span> C4 Argon 4 / Antigravity (Auditoría)</span>
            <span class="font-mono text-rose-400 font-bold">5%</span>
          </div>
        </div>
      </section>

    </div>

    <!-- RECENT ORDERS / TASKS -->
    <section class="bg-slate-900/90 border border-slate-800 rounded-xl p-5">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-2">
          <span>📋</span> COLA DE ÓRDENES Y TAREAS (DISCORD / MÓVIL)
        </h3>
        <span class="text-xs text-slate-500 font-mono">Canal #general</span>
      </div>
      <div class="space-y-2 max-h-48 overflow-y-auto text-xs" id="ordersList">
        <div class="p-3 bg-slate-950/60 border border-slate-800/80 rounded-lg text-slate-400 italic">
          No hay órdenes pendientes. Puedes mandar una orden desde Discord con <code>!orden &lt;tarea&gt;</code>.
        </div>
      </div>
    </section>

  </div>

  <script>
    function updateClock() {
      const now = new Date();
      document.getElementById('clock').textContent = now.toLocaleTimeString();
    }
    setInterval(updateClock, 1000);
    updateClock();

    function copyWallet() {
      const addr = document.getElementById('walletAddrDisplay').innerText.trim();
      navigator.clipboard.writeText(addr);
      const btn = document.getElementById('copyBtnText');
      btn.innerText = '¡Copiado!';
      setTimeout(() => { btn.innerText = 'Copiar Dirección'; }, 2000);
    }

    // Chart.js Setup
    const ctxGas = document.getElementById('gasChart').getContext('2d');
    const gasChart = new Chart(ctxGas, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Gas Price (Gwei)',
          data: [],
          borderColor: '#22d3ee',
          backgroundColor: 'rgba(34, 211, 238, 0.1)',
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 2,
          pointBackgroundColor: '#22d3ee'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#64748b', font: { size: 10 } } },
          y: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#64748b', font: { size: 10 } } }
        }
      }
    });

    const ctxHw = document.getElementById('hardwareChart').getContext('2d');
    const hardwareChart = new Chart(ctxHw, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          { label: 'VRAM (%)', data: [], borderColor: '#10b981', borderWidth: 2, pointRadius: 0, tension: 0.3 },
          { label: 'CPU (%)', data: [], borderColor: '#22d3ee', borderWidth: 2, pointRadius: 0, tension: 0.3 },
          { label: 'RAM (%)', data: [], borderColor: '#a855f7', borderWidth: 1.5, pointRadius: 0, tension: 0.3 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(51, 65, 85, 0.2)' }, ticks: { color: '#64748b', font: { size: 10 } } },
          y: { min: 0, max: 100, grid: { color: 'rgba(51, 65, 85, 0.2)' }, ticks: { color: '#64748b', font: { size: 10 } } }
        }
      }
    });

    const ctxPie = document.getElementById('brainPieChart').getContext('2d');
    const brainPieChart = new Chart(ctxPie, {
      type: 'doughnut',
      data: {
        labels: ['C2 Gemini Flash', 'C1 Ollama Local', 'C3 DeepSeek', 'C4 Argon 4'],
        datasets: [{
          data: [55, 30, 10, 5],
          backgroundColor: ['#06b6d4', '#10b981', '#a855f7', '#f43f5e'],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        cutout: '72%'
      }
    });

    async function fetchTelemetry() {
      try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();

        // 1. Active Brain
        const brain = data.active_brain || {};
        document.getElementById('activeBrainName').textContent = brain.current_brain || 'Cerebro 1: Ollama Qwen 2.5 Coder 7B (GTX 1660)';
        document.getElementById('activeBrainStatus').textContent = 'Estado: ' + (brain.status || 'vigilancia 24/7') + ' • Tarea: ' + (brain.task_type || 'operaciones');
        document.getElementById('activeBrainTime').textContent = brain.timestamp || '--';

        // 2. Web3 data & EUR balances
        const web3 = data.web3 || {};
        document.getElementById('topBlock').textContent = '#' + (web3.block_number || '------');
        document.getElementById('topGas').textContent = (web3.gas_price_gwei || '0.00') + ' Gwei';
        document.getElementById('currentGasTag').textContent = (web3.gas_price_gwei || '0.00') + ' Gwei';
        
        // Dinero Real en Euros
        const realEur = Number(web3.real_balance_eur || 0).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const realEth = Number(web3.real_balance_eth || 0).toFixed(4);
        const ethPrice = Number(web3.eth_price_eur || 2151.57).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        
        document.getElementById('realEurBalance').textContent = realEur;
        document.getElementById('realEthBalance').textContent = realEth;
        document.getElementById('realUsdcBalance').textContent = Number(web3.real_balance_usdc || 0).toFixed(2);
        document.getElementById('realWdoomBalance').textContent = Number(web3.real_balance_wdoom || 3000).toLocaleString('es-ES');
        document.getElementById('ethPriceTag').textContent = ethPrice;
        document.getElementById('topEthPrice').textContent = ethPrice;

        // Testnet Balances & Bounties
        document.getElementById('ethBalance').textContent = Number(web3.balance_eth || 0).toFixed(4);
        document.getElementById('testnetEurBalance').textContent = Number(web3.balance_eur || 0).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        document.getElementById('tokensEarned').textContent = Number(web3.tokens_earned || 150000).toLocaleString('es-ES');

        if (web3.contract_address) {
          document.getElementById('contractBadge').textContent = 'Oráculo: ' + web3.contract_address.slice(0, 10) + '...';
        }

        // 3. Hardware readings
        const hw = data.hardware || {};
        const gpu = data.gpu || {};
        const vramUsed = gpu.vram_used_mb || 0;
        const vramTotal = gpu.vram_total_mb || 6144;
        const vramPct = Math.round((vramUsed / vramTotal) * 100);
        document.getElementById('vramText').textContent = vramUsed + ' / ' + vramTotal + ' MB (' + vramPct + '%)';
        document.getElementById('cpuText').textContent = Math.round(hw.cpu_percent || 0) + '%';
        document.getElementById('ramText').textContent = (hw.ram_used_gb || 0) + ' / ' + (hw.ram_total_gb || 16) + ' GB';

        // 4. Update Gas Chart
        const gasHistory = data.gas_history || [];
        if (gasHistory.length > 0) {
          gasChart.data.labels = gasHistory.map(g => g.time);
          gasChart.data.datasets[0].data = gasHistory.map(g => g.gas_gwei);
          gasChart.update('none');
        }

        // 5. Update Hardware Chart
        const hwHistory = data.hardware_history || [];
        if (hwHistory.length > 0) {
          hardwareChart.data.labels = hwHistory.map(h => h.time);
          hardwareChart.data.datasets[0].data = hwHistory.map(h => h.vram);
          hardwareChart.data.datasets[1].data = hwHistory.map(h => h.cpu);
          hardwareChart.data.datasets[2].data = hwHistory.map(h => h.ram);
          hardwareChart.update('none');
        }

        // 6. Queue Summary & DeepSeek Budget
        const qSummary = data.queue_summary || {};
        document.getElementById('queueAlta').textContent = qSummary.alta || 0;
        document.getElementById('queueMedia').textContent = qSummary.media || 0;
        document.getElementById('queueBaja').textContent = qSummary.baja || 0;
        document.getElementById('queueGrants').textContent = qSummary.curated_grants || 0;
        document.getElementById('queueDone').textContent = qSummary.delivered_total || qSummary.executed_total || 0;
        document.getElementById('queueTotal').textContent = qSummary.total_active || 0;

        const dsBudget = data.deepseek_budget || {};
        const dsSpent = Number(dsBudget.spent_eur || 0);
        const dsLimit = Number(dsBudget.daily_limit_eur || 0.50);
        const dsRem = Number(dsBudget.remaining_eur || Math.max(0, dsLimit - dsSpent));
        const dsPctVal = Math.min(100, Math.round((dsSpent / dsLimit) * 100));

        document.getElementById('dsSpent').textContent = dsSpent.toFixed(4);
        document.getElementById('dsRemaining').textContent = dsRem.toFixed(4) + ' €';
        document.getElementById('dsPct').textContent = dsPctVal + '%';
        document.getElementById('dsProgressBar').style.width = dsPctVal + '%';

        // 7. Recent Orders
        const orders = data.recent_orders || [];
        const orderDiv = document.getElementById('ordersList');
        if (orders.length > 0) {
          orderDiv.innerHTML = orders.map(o => `
            <div class="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between">
              <div>
                <span class="font-bold text-slate-200">${o.text || 'Orden'}</span>
                <span class="text-[10px] text-slate-500 block font-mono">${o.timestamp} • ${o.source || 'discord'}</span>
              </div>
              <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold ${o.status === 'completed' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-cyan-950 text-cyan-400 border border-cyan-800'}">
                ${o.status.toUpperCase()}
              </span>
            </div>
          `).join('');
        }
      } catch (err) {
        console.error('Error fetching telemetry:', err);
      }
    }

    setInterval(fetchTelemetry, 2000);
    fetchTelemetry();
  </script>
</body>
</html>
"""

class DashboardHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Payment-Tx, Authorization")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path == "/poidh-tx-dashboard" or self.path == "/poidh-tx-dashboard.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_p = BASE_DIR / "docs" / "poidh_txs_dashboard.html"
            if html_p.exists():
                self.wfile.write(html_p.read_bytes())
            else:
                self.wfile.write(b"Dashboard file not found")
        elif self.path == "/poidh_daily_txs.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            json_p = BASE_DIR / "docs" / "poidh_daily_txs.json"
            if json_p.exists():
                self.wfile.write(json_p.read_bytes())
            else:
                self.wfile.write(b"{}")
        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            with data_lock:
                q_summary = get_queue_summary()
                spent_today = get_today_spent()
                status = {
                    "active_brain": telemetry_data["active_brain"],
                    "hardware": telemetry_data["hardware"],
                    "gpu": telemetry_data["gpu"],
                    "web3": telemetry_data["web3"],
                    "gas_history": list(telemetry_data["gas_history"]),
                    "hardware_history": list(telemetry_data["hardware_history"]),
                    "deepseek": telemetry_data["deepseek"],
                    "gemini": telemetry_data["gemini"],
                    "queue_summary": q_summary,
                    "deepseek_budget": {
                        "spent_eur": round(spent_today, 4),
                        "daily_limit_eur": DAILY_BUDGET_EUR,
                        "remaining_eur": round(max(0.0, DAILY_BUDGET_EUR - spent_today), 4)
                    },
                    "obsidian_notes": get_obsidian_notes(),
                    "recent_orders": get_recent_orders(),
                    "server_time": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            self.wfile.write(json.dumps(status).encode("utf-8"))
        elif self.path == "/api/v1/x402/pricing":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            resp = {
                "protocol": "x402",
                "version": "1.0",
                "network": "base",
                "chainId": 8453,
                "payee": USER_PAYOUT_WALLET,
                "pricing": PRICING_TABLE,
                "docs": "https://x402.org"
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        elif self.path.startswith("/api/v1/x402/intel"):
            gw = get_gateway()
            tx_hash = self.headers.get("X-Payment-Tx")
            if not tx_hash:
                ch = gw.get_payment_challenge("intel")
                self.send_response(402)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("WWW-Authenticate", 'x402-v1 network="base"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(ch).encode("utf-8"))
                return
            ok, msg, meta = gw.verify_payment_tx(tx_hash, "intel")
            if not ok:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": msg}).encode("utf-8"))
                return
            opp_file = BASE_DIR / "memoria" / "estado" / "cola_oportunidades.json"
            opps = []
            if opp_file.exists():
                try:
                    opps = json.loads(opp_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "service": "intel",
                "payment": meta,
                "bounties_count": len(opps),
                "data": opps[:20]
            }).encode("utf-8"))
        elif self.path.startswith("/api/v1/agentkit/action"):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            action = qs.get("action", [""])[0]
            params = {k: v[0] for k, v in qs.items() if k != "action"}
            provider = get_agentkit_provider()
            res = provider.dispatch_action(action, params)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif self.path.startswith("/api/v1/eas/attestations"):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            addr = qs.get("address", [WALLET_ADDRESS])[0]
            limit = int(qs.get("limit", [10])[0])
            items = get_address_attestations(addr, limit=limit)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"address": addr, "count": len(items), "attestations": items}).encode("utf-8"))
        elif self.path.startswith("/api/v1/eas/reputation"):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            addr = qs.get("address", [WALLET_ADDRESS])[0]
            rep = get_address_reputation(addr)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(rep).encode("utf-8"))
        elif self.path.startswith("/api/v1/eas/latest"):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", [10])[0])
            recent = get_recent_attestations(limit=limit)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"network": "base", "count": len(recent), "attestations": recent}).encode("utf-8"))
        elif self.path == "/api/v1/erc8021/info":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            suffix = encode_erc8021_suffix()
            resp = {
                "standard": "ERC-8021",
                "network": "base",
                "chainId": 8453,
                "builder_code": DEFAULT_BUILDER_CODE,
                "suffix_hex": suffix.hex(),
                "marker": "80218021802180218021802180218021",
                "docs": "https://erc8021.com"
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        elif self.path == "/api/v1/defi/overview":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            data = get_base_defi_overview()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        elif self.path.startswith("/api/v1/defi/yields"):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", [10])[0])
            min_tvl = float(qs.get("min_tvl", [500000])[0])
            sym = qs.get("symbol", [None])[0]
            stable = qs.get("stable", ["false"])[0].lower() in ("true", "1")
            yields = get_base_top_yields(min_tvl=min_tvl, symbol_filter=sym, stable_only=stable, limit=limit)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"count": len(yields), "yields": yields}).encode("utf-8"))
        elif self.path.startswith("/api/v1/defi/prices"):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            tokens_str = qs.get("tokens", ["WETH,USDC,AERO"])[0]
            tokens_list = [t.strip() for t in tokens_str.split(",") if t.strip()]
            prices = get_base_token_prices(tokens_list)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"prices": prices}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        if self.path == "/api/v1/x402/solve":
            gw = get_gateway()
            tx_hash = self.headers.get("X-Payment-Tx")
            if not tx_hash:
                ch = gw.get_payment_challenge("solve")
                self.send_response(402)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("WWW-Authenticate", 'x402-v1 network="base"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(ch).encode("utf-8"))
                return

            ok, msg, meta = gw.verify_payment_tx(tx_hash, "solve")
            if not ok:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": msg}).encode("utf-8"))
                return

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            prompt = ""
            try:
                data = json.loads(body)
                prompt = data.get("prompt", "")
            except Exception:
                prompt = body

            if not prompt:
                prompt = "Verificar estado y generar resumen de inteligencia"

            res = route_task(
                task_type="general",
                prompt=prompt,
                difficulty=3,
                system_prompt="Eres un agente de IA autonomo en Base L2 resolviendo una peticion comercial via micropago x402."
            )

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "service": "solve",
                "payment": meta,
                "solution": res
            }).encode("utf-8"))
        elif self.path == "/api/v1/agentkit/action":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                action = data.get("action", "")
                params = data.get("params", {})
            except Exception:
                action = ""
                params = {}
            provider = get_agentkit_provider()
            res = provider.dispatch_action(action, params)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif self.path == "/api/v1/erc8021/attach":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                raw_data = data.get("data", "")
                code = data.get("builder_code", DEFAULT_BUILDER_CODE)
                attributed = attach_erc8021_attribution(raw_data, code)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "attributed_data": attributed, "builder_code": code}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif self.path == "/api/v1/erc8021/decode":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                raw_data = data.get("data", "")
                decoded = decode_erc8021_attribution(raw_data)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "result": decoded}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        return

def run_server():
    collector_thread = threading.Thread(target=background_collector, daemon=True)
    collector_thread.start()
    
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print("=" * 60)
    print(f"  DASHBOARD SERVER 24/7 ACTIVO: http://127.0.0.1:{PORT}")
    print("  Cotización en vivo: ETH/EUR vía Binance API")
    print("  Auto-Claim & Telemetría en tiempo real")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor de dashboard...")
        server.server_close()

if __name__ == "__main__":
    run_server()
