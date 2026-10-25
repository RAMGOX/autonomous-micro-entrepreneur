"""
Dashboard Server v3.0 (Mobile-First Command Center & Official x402 Gateway):
- 100% métricas reales verificadas on-chain y en APIs (cero saldos simulados de Sepolia).
- Interfaz Mobile-First con 4 pestañas táctiles (Resumen, Revisar, Motores, Prompts/Obsidian).
- Acceso móvil privado mediante token HMAC (?auth=...) enviado al Discord del propietario;
  acceso local directo en 127.0.0.1:8080; vista pública segura para clientes x402 externos.
"""
import os
import sys
import json
import time
import hmac
import hashlib
import threading
import subprocess
import urllib.request
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))
ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from opportunity_queue import get_queue_summary, load_queue, score_opportunity_cost_benefit
from review_queue import load_reviews, update_review_decision, get_review_by_id
from brain_router import (
    get_today_spent,
    get_deepseek_real_balance,
    get_gemini_status,
    DAILY_BUDGET_EUR,
    route_task
)
from x402_gateway import get_gateway, PRICING_TABLE, USER_PAYOUT_WALLET, extract_clean_webpage
from agentkit_actions import get_agentkit_provider
from eas_indexer import get_address_attestations, get_address_reputation, get_recent_attestations
from erc8021_builder import encode_erc8021_suffix, attach_erc8021_attribution, decode_erc8021_attribution, DEFAULT_BUILDER_CODE
from defillama_engine import get_base_top_yields, get_base_token_prices, get_base_defi_overview
from dex_scanner import get_base_trending_pools, get_base_new_pools, get_base_token_market_data
from treasury_yield_manager import get_treasury_status, get_recommended_allocations, simulate_yield_cashflow
from poidh_claim_submitter import submit_approved_poidh_claim

PORT = 8080
BOT_WALLET = os.getenv("PUBLIC_ADDRESS_TESTNET", "0x02c1F87F514493F359Afc0B3ff6b587434770361")
BASE_MAINNET_RPC = "https://mainnet.base.org"
USDC_MAINNET_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
ERC20_BALANCE_ABI = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}]


def get_mobile_access_token() -> str:
    """Genera un token determinista de 12 caracteres derivado de las claves privadas para el enlace móvil de Discord."""
    seed = (os.getenv("DISCORD_BOT_TOKEN", "") + os.getenv("PRIVATE_KEY_TESTNET", "ame_v3")).encode("utf-8")
    return hmac.new(seed, b"ame_mobile_dashboard_v3", hashlib.sha256).hexdigest()[:12]


MOBILE_TOKEN = get_mobile_access_token()
data_lock = threading.Lock()

telemetry_data = {
    "finance": {
        "user_wallet": USER_PAYOUT_WALLET,
        "user_eth": 0.0,
        "user_usdc": 0.0,
        "user_eur": 0.0,
        "bot_wallet": BOT_WALLET,
        "bot_eth": 0.0,
        "bot_usdc": 0.0,
        "bot_eur": 0.0,
        "bot_txs_left": 0,
        "eth_price_eur": 2250.0,
        "base_block": 0,
        "gas_gwei": 0.005,
        "last_update": "--:--:--"
    },
    "hardware": {"cpu_percent": 0.0, "ram_used_gb": 0.0, "ram_total_gb": 16.0, "ram_percent": 0.0},
    "gpu": {"vram_used_mb": 0, "vram_total_mb": 6144, "gpu_util_percent": 0, "temp_c": 0},
    "active_brain": {"current_brain": "Sistema en Reposo (0W GPU)", "status": "en espera", "task_type": "vigilancia", "timestamp": "--"}
}


def get_eth_eur_price() -> float:
    try:
        req = urllib.request.Request("https://api.binance.com/api/v3/ticker/price?symbol=ETHEUR", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return round(float(json.loads(r.read().decode()).get("price", 2250.0)), 2)
    except Exception:
        return 2250.0


def get_gpu_stats():
    try:
        cmd = ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"]
        out = subprocess.check_output(cmd, encoding="utf-8", creationflags=0x08000000).strip()
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
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
            "ram_used_gb": round(mem.used / (1024**3), 1),
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "ram_percent": round(mem.percent, 1)
        }
    except Exception:
        return {"cpu_percent": 0.0, "ram_used_gb": 0.0, "ram_total_gb": 16.0, "ram_percent": 0.0}


def get_active_brain_data():
    p = BASE_DIR / "memoria" / "estado" / "cerebro_activo.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"current_brain": "Sistema en Reposo (0W GPU)", "status": "en espera", "task_type": "vigilancia", "timestamp": time.strftime("%H:%M:%S")}


def get_watchdog_health():
    p = BASE_DIR / "memoria" / "estado" / "sistema_salud.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def get_public_tunnel_url() -> str:
    p = BASE_DIR / "memoria" / "estado" / "public_url.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("public_url", "")
        except Exception:
            pass
    return ""


def get_apify_actors():
    p = BASE_DIR / "memoria" / "estado" / "apify_actors_status.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def background_collector():
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(BASE_MAINNET_RPC, request_kwargs={"timeout": 4}))
    usdc_ctr = w3.eth.contract(address=Web3.to_checksum_address(USDC_MAINNET_ADDRESS), abi=ERC20_BALANCE_ABI)

    last_web3_ts = 0.0
    last_price_ts = 0.0
    eth_eur = 2250.0

    while True:
        try:
            now = time.time()
            if now - last_price_ts > 60:
                eth_eur = get_eth_eur_price()
                last_price_ts = now

            gpu = get_gpu_stats()
            hw = get_cpu_ram()
            brain = get_active_brain_data()

            fin_update = None
            if now - last_web3_ts > 12:
                last_web3_ts = now
                try:
                    u_addr = Web3.to_checksum_address(USER_PAYOUT_WALLET)
                    b_addr = Web3.to_checksum_address(BOT_WALLET)

                    blk = w3.eth.block_number
                    gas_wei = w3.eth.gas_price
                    gas_gwei = round(float(w3.from_wei(gas_wei, "gwei")), 4)

                    u_eth = float(w3.from_wei(w3.eth.get_balance(u_addr), "ether"))
                    u_usdc = float(usdc_ctr.functions.balanceOf(u_addr).call()) / 1e6
                    b_eth = float(w3.from_wei(w3.eth.get_balance(b_addr), "ether"))
                    b_usdc = float(usdc_ctr.functions.balanceOf(b_addr).call()) / 1e6

                    u_eur = round((u_eth * eth_eur) + (u_usdc * 0.92), 2)
                    b_eur = round((b_eth * eth_eur) + (b_usdc * 0.92), 2)
                    tx_cost_eth = max(0.0000035, float(w3.from_wei(gas_wei * 140000, "ether")))
                    txs_left = int(b_eth / tx_cost_eth) if b_eth > 0 else 0

                    fin_update = {
                        "user_wallet": USER_PAYOUT_WALLET,
                        "user_eth": round(u_eth, 6),
                        "user_usdc": round(u_usdc, 2),
                        "user_eur": u_eur,
                        "bot_wallet": BOT_WALLET,
                        "bot_eth": round(b_eth, 6),
                        "bot_usdc": round(b_usdc, 2),
                        "bot_eur": b_eur,
                        "bot_txs_left": txs_left,
                        "eth_price_eur": eth_eur,
                        "base_block": blk,
                        "gas_gwei": gas_gwei,
                        "last_update": time.strftime("%H:%M:%S")
                    }
                except Exception:
                    pass

            with data_lock:
                telemetry_data["gpu"] = gpu
                telemetry_data["hardware"] = hw
                telemetry_data["active_brain"] = brain
                if fin_update:
                    telemetry_data["finance"] = fin_update
        except Exception:
            pass
        time.sleep(3)


MOBILE_APP_HTML = """<!DOCTYPE html>
<html lang="es" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <title>AME v3 • Mando Móvil 24/7</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { background: #060911; color: #f1f5f9; -webkit-tap-highlight-color: transparent; padding-bottom: 84px; }
    .glass { background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(12px); border: 1px solid rgba(51, 65, 85, 0.6); }
    .tab-active { color: #22d3ee; border-top: 2px solid #22d3ee; background: rgba(8, 145, 178, 0.12); }
  </style>
</head>
<body class="font-sans antialiased">

  <!-- HEADER COMPACTO MÓVIL + DESKTOP -->
  <header class="sticky top-0 z-30 glass px-4 py-3 border-b border-slate-800">
    <div class="max-w-5xl mx-auto flex items-center justify-between">
      <div class="flex items-center gap-2.5">
        <span class="relative flex h-3 w-3">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
        </span>
        <div>
          <h1 class="text-sm md:text-base font-extrabold tracking-tight text-white">AME v3 • MANDO 24/7</h1>
          <p id="subHeader" class="text-[11px] text-slate-400 font-mono">Cargando telemetría real...</p>
        </div>
      </div>
      <button onclick="refreshAll()" class="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-cyan-300 border border-slate-700 active:scale-95 transition">
        Actualizar
      </button>
    </div>
  </header>

  <main class="max-w-5xl mx-auto p-3 md:p-6 space-y-4">

    <!-- TAB 1: RESUMEN EJECUTIVO REAL -->
    <section id="tab-resumen" class="space-y-4">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="glass rounded-2xl p-3.5">
          <div class="text-[11px] text-slate-400 uppercase font-bold">Tu Cartera Coinbase</div>
          <div id="userEur" class="text-2xl font-black text-emerald-400 mt-1">0.00 €</div>
          <div id="userCrypto" class="text-[11px] text-slate-400 font-mono mt-0.5">0 USDC • 0 ETH</div>
        </div>
        <div class="glass rounded-2xl p-3.5">
          <div class="text-[11px] text-slate-400 uppercase font-bold">DeepSeek Hoy (Máx 0.50€)</div>
          <div id="dsSpent" class="text-2xl font-black text-cyan-300 mt-1">0.00 €</div>
          <div class="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
            <div id="dsBar" class="bg-cyan-400 h-full transition-all" style="width:0%"></div>
          </div>
          <div id="dsBalance" class="text-[11px] text-slate-400 font-mono mt-1">Saldo API: $-- USD</div>
        </div>
        <div class="glass rounded-2xl p-3.5">
          <div class="text-[11px] text-slate-400 uppercase font-bold">Para Revisar</div>
          <div id="pendingRevCount" class="text-2xl font-black text-amber-400 mt-1">0</div>
          <div class="text-[11px] text-slate-400 mt-0.5">Esperando tu OK</div>
        </div>
        <div class="glass rounded-2xl p-3.5">
          <div class="text-[11px] text-slate-400 uppercase font-bold">Gas Operativo Base</div>
          <div id="botGasEth" class="text-xl font-black text-slate-100 mt-1">0.0004 ETH</div>
          <div id="botTxsLeft" class="text-[11px] text-emerald-400 font-mono mt-0.5">~110 TXs disp.</div>
        </div>
      </div>

      <!-- CEREBROS IA -->
      <div class="glass rounded-2xl p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-bold uppercase text-cyan-400">Jerarquía Multi-IA Activa</span>
          <span id="brainClock" class="text-[11px] font-mono text-slate-400">--:--:--</span>
        </div>
        <div id="currentBrainBanner" class="text-sm font-bold text-white bg-slate-900/90 border border-slate-800 rounded-xl p-3 font-mono">
          Sistema en Reposo (0W GPU)
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3 text-xs">
          <div class="bg-slate-900/70 p-2.5 rounded-xl border border-slate-800">
            <div class="font-bold text-purple-300">Argon 4 (Pro)</div>
            <div class="text-[11px] text-slate-400">Chats paralelos 0€</div>
          </div>
          <div class="bg-slate-900/70 p-2.5 rounded-xl border border-slate-800">
            <div class="font-bold text-cyan-300">DeepSeek V3/R1</div>
            <div class="text-[11px] text-slate-400">Tope 0.50€/día</div>
          </div>
          <div class="bg-slate-900/70 p-2.5 rounded-xl border border-slate-800">
            <div class="font-bold text-amber-300">Gemini Flash</div>
            <div id="gemState" class="text-[11px] text-slate-400">Temporal 0€</div>
          </div>
          <div class="bg-slate-900/70 p-2.5 rounded-xl border border-slate-800">
            <div class="font-bold text-emerald-300">Ollama GTX 1660</div>
            <div id="gpuIdleState" class="text-[11px] text-slate-400">0% Reposo</div>
          </div>
        </div>
      </div>

      <!-- SALUD SERVIDOR 24/7 -->
      <div class="glass rounded-2xl p-4 space-y-3">
        <div class="text-xs font-bold uppercase text-slate-300">Salud del Servidor Casa 24/7</div>
        <div id="pillarsGrid" class="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs font-mono"></div>
        <div class="grid grid-cols-3 gap-2 pt-1 text-center text-xs font-mono">
          <div class="bg-slate-900/80 rounded-xl p-2 border border-slate-800">CPU: <span id="hwCpu" class="text-white font-bold">0%</span></div>
          <div class="bg-slate-900/80 rounded-xl p-2 border border-slate-800">RAM: <span id="hwRam" class="text-white font-bold">0%</span></div>
          <div class="bg-slate-900/80 rounded-xl p-2 border border-slate-800">GPU: <span id="hwGpu" class="text-emerald-400 font-bold">0%</span></div>
        </div>
      </div>
    </section>

    <!-- TAB 2: BANDEJA DE REVISIÓN MÓVIL -->
    <section id="tab-revisar" class="hidden space-y-3">
      <div class="glass rounded-2xl p-4">
        <h2 class="text-sm font-bold text-white">📱 Bandeja de Aprobación Móvil</h2>
        <p class="text-xs text-slate-400 mt-0.5">Nada gasta gas ni se publica fuera sin tu OK aquí o en Discord.</p>
      </div>
      <div id="reviewsContainer" class="space-y-3"></div>
    </section>

    <!-- TAB 3: LOS 3 MOTORES DE INGRESOS -->
    <section id="tab-motores" class="hidden space-y-4">
      <div class="glass rounded-2xl p-4 space-y-3">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-bold text-emerald-400">🎯 Motor 1: Bounties Código GitHub / Algora</h2>
          <span id="ghCount" class="text-xs font-mono bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded">0 activos</span>
        </div>
        <div id="ghList" class="space-y-2 text-xs"></div>
      </div>

      <div class="glass rounded-2xl p-4 space-y-3">
        <h2 class="text-sm font-bold text-cyan-400">🏭 Motor 2: Actors Apify Store + MCP (80% USD)</h2>
        <div id="apifyList" class="space-y-2 text-xs"></div>
      </div>

      <div class="glass rounded-2xl p-4 space-y-2">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-bold text-indigo-400">⚡ Motor 3: Pasarela x402 Scraping Residencial</h2>
          <span id="x402Sales" class="text-xs font-mono bg-indigo-950 text-indigo-300 px-2 py-0.5 rounded">0 ventas</span>
        </div>
        <p class="text-xs text-slate-400">Extracción web antibot pagada en USDC/ETH directo a tu Coinbase Wallet.</p>
        <div id="tunnelBox" class="text-[11px] font-mono bg-slate-900 p-2.5 rounded-xl border border-slate-800 break-all text-cyan-300"></div>
      </div>
    </section>

    <!-- TAB 4: PROMPTS CHATS PARALELOS & OBSIDIAN -->
    <section id="tab-prompts" class="hidden space-y-4">
      <div class="glass rounded-2xl p-4 space-y-3">
        <h2 class="text-sm font-bold text-purple-300">🤖 Prompts para tus Chats Paralelos (Gemini Pro)</h2>
        <p class="text-xs text-slate-400">Copia y pega cualquiera de estos prompts en otro chat de tu cuenta Pro con <code class="text-cyan-300">/schedule</code> o <code class="text-cyan-300">/goal</code> para multiplicar producción a coste 0€:</p>

        <div class="bg-slate-900 rounded-xl p-3 border border-slate-800 space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white">Prompt Chat Obrero A (Solucionador Bounties GitHub)</span>
            <button onclick="copyText('promptWorkerA')" class="px-2.5 py-1 bg-purple-600 text-white rounded-lg text-[11px] font-bold">Copiar</button>
          </div>
          <pre id="promptWorkerA" class="text-[11px] text-slate-300 whitespace-pre-wrap font-mono bg-slate-950 p-2.5 rounded-lg">Trabaja en C:\\Users\\Antonio Ramos\\autonomous-micro-entrepreneur. Lee memoria/estado/cola_oportunidades.json y MOTOR_1_BOUNTIES_GITHUB.md. Selecciona el mejor bounty abierto de código (Python/TS/JS/Web3) que no esté ya en bandeja_revision.json, analiza el repositorio real, desarrolla una solución limpia y verificada con tests locales sin hacer spam ni abrir PR automático, guarda el entregable en memoria/estrategias/soluciones_propuestas/ y regístralo con src/review_queue.py (push_for_review) para mi aprobación móvil en Discord.</pre>
        </div>

        <div class="bg-slate-900 rounded-xl p-3 border border-slate-800 space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white">Prompt Chat Obrero B (Creador & Mantenimiento Apify Store)</span>
            <button onclick="copyText('promptWorkerB')" class="px-2.5 py-1 bg-cyan-600 text-white rounded-lg text-[11px] font-bold">Copiar</button>
          </div>
          <pre id="promptWorkerB" class="text-[11px] text-slate-300 whitespace-pre-wrap font-mono bg-slate-950 p-2.5 rounded-lg">Trabaja en C:\\Users\\Antonio Ramos\\autonomous-micro-entrepreneur. Ejecuta src/apify_actor_factory.py para verificar la salud de los Actors actuales. Después investiga un nuevo nicho B2B con baja competencia en Apify Store (datos públicos europeos, e-commerce o herramientas MCP para agentes), construye y prueba con datos reales en local un nuevo Actor completo dentro de apify_actors/, y envíalo mediante src/review_queue.py (push_for_review) a mi Discord para aprobar su subida.</pre>
        </div>
      </div>
    </section>

  </main>

  <!-- NAVEGACIÓN INFERIOR TÁCTIL MÓVIL -->
  <nav class="fixed bottom-0 inset-x-0 z-40 glass border-t border-slate-800">
    <div class="max-w-5xl mx-auto grid grid-cols-4 text-center">
      <button onclick="switchTab('resumen')" id="nav-resumen" class="py-3 text-xs font-bold tab-active">📊 Resumen</button>
      <button onclick="switchTab('revisar')" id="nav-revisar" class="py-3 text-xs font-bold text-slate-400">✅ Revisar <span id="navBadge" class="ml-0.5 px-1.5 py-0.2 bg-amber-500 text-black rounded-full text-[10px] hidden">0</span></button>
      <button onclick="switchTab('motores')" id="nav-motores" class="py-3 text-xs font-bold text-slate-400">🎯 Motores</button>
      <button onclick="switchTab('prompts')" id="nav-prompts" class="py-3 text-xs font-bold text-slate-400">🧠 Prompts</button>
    </div>
  </nav>

  <script>
    const urlParams = new URLSearchParams(window.location.search);
    const authKey = urlParams.get("auth") || localStorage.getItem("ame_auth") || "";
    if (urlParams.get("auth")) localStorage.setItem("ame_auth", urlParams.get("auth"));

    function switchTab(name) {
      ["resumen", "revisar", "motores", "prompts"].forEach(t => {
        document.getElementById("tab-" + t).classList.toggle("hidden", t !== name);
        const btn = document.getElementById("nav-" + t);
        if (t === name) { btn.classList.add("tab-active"); btn.classList.remove("text-slate-400"); }
        else { btn.classList.remove("tab-active"); btn.classList.add("text-slate-400"); }
      });
    }

    function copyText(id) {
      navigator.clipboard.writeText(document.getElementById(id).innerText);
      alert("Prompt copiado al portapapeles");
    }

    async function decideReview(revId, decision) {
      let feedback = "";
      if (decision === "changes_requested") {
        feedback = prompt("¿Qué cambio quieres que aplique la IA?") || "";
        if (!feedback) return;
      }
      const r = await fetch("/api/v1/reviews/decide?auth=" + encodeURIComponent(authKey), {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ id: revId, decision, feedback })
      });
      const res = await r.json();
      alert(res.message || "Actualizado");
      refreshAll();
    }

    async function refreshAll() {
      try {
        const r = await fetch("/api/status?auth=" + encodeURIComponent(authKey));
        const d = await r.json();

        const fin = d.finance || {};
        document.getElementById("subHeader").textContent = `Base #${fin.base_block || '--'} • ETH ${fin.eth_price_eur || '--'}€ • ${d.server_time || ''}`;
        document.getElementById("userEur").textContent = `${(fin.user_eur || 0).toFixed(2)} €`;
        document.getElementById("userCrypto").textContent = `${fin.user_usdc || 0} USDC • ${fin.user_eth || 0} ETH`;

        const ds = d.deepseek || {};
        const spent = ds.spent_today_eur || 0;
        const lim = ds.daily_limit_eur || 0.5;
        document.getElementById("dsSpent").textContent = `${spent.toFixed(4)} €`;
        document.getElementById("dsBar").style.width = `${Math.min(100, (spent / lim) * 100)}%`;
        document.getElementById("dsBalance").textContent = `Saldo real: $${ds.balance_usd ?? '--'} USD`;

        document.getElementById("botGasEth").textContent = `${fin.bot_eth || 0} ETH`;
        document.getElementById("botTxsLeft").textContent = `~${fin.bot_txs_left || 0} TXs disponibles`;

        const br = d.active_brain || {};
        document.getElementById("currentBrainBanner").textContent = `${br.current_brain || 'En espera'} • ${br.status || ''}`;
        document.getElementById("brainClock").textContent = br.timestamp || "";
        document.getElementById("gemState").textContent = (d.gemini || {}).status || "temporal";

        const gpu = d.gpu || {};
        const hw = d.hardware || {};
        document.getElementById("gpuIdleState").textContent = `${gpu.gpu_util_percent || 0}% uso • ${gpu.temp_c || 0}°C`;
        document.getElementById("hwCpu").textContent = `${hw.cpu_percent || 0}%`;
        document.getElementById("hwRam").textContent = `${hw.ram_percent || 0}%`;
        document.getElementById("hwGpu").textContent = `${gpu.gpu_util_percent || 0}% (${gpu.temp_c || 0}°C)`;

        // Pilares Watchdog
        const wd = d.watchdog || {};
        const pillars = [
          ["Dashboard", true],
          ["Discord", wd.discord_bot !== false],
          ["Daemon", wd.autonomous_daemon !== false],
          ["Túnel Móvil", wd.public_tunnel !== false],
          ["Ollama Respaldo", wd.ollama !== false]
        ];
        document.getElementById("pillarsGrid").innerHTML = pillars.map(([name, ok]) =>
          `<div class="px-2.5 py-2 rounded-xl border ${ok ? 'bg-emerald-950/40 border-emerald-800/70 text-emerald-300' : 'bg-red-950/50 border-red-800 text-red-300'} flex items-center justify-between"><span>${name}</span><span>${ok ? 'ON' : 'OFF'}</span></div>`
        ).join("");

        // Reviews
        const revs = d.pending_reviews || [];
        document.getElementById("pendingRevCount").textContent = revs.length;
        const badge = document.getElementById("navBadge");
        badge.textContent = revs.length;
        badge.classList.toggle("hidden", revs.length === 0);

        if (revs.length === 0) {
          document.getElementById("reviewsContainer").innerHTML = `<div class="glass rounded-2xl p-6 text-center text-xs text-slate-400">No hay entregas pendientes de revisión ahora mismo.</div>`;
        } else {
          document.getElementById("reviewsContainer").innerHTML = revs.map(rv => `
            <div class="glass rounded-2xl p-4 space-y-2.5 border border-amber-500/30">
              <div class="flex items-start justify-between gap-2">
                <div>
                  <span class="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">${rv.category}</span>
                  <h3 class="text-sm font-bold text-white mt-1">${rv.title}</h3>
                </div>
                <span class="text-xs font-extrabold text-emerald-400 shrink-0">${rv.reward_display || ''}</span>
              </div>
              <p class="text-xs text-slate-300 whitespace-pre-line">${rv.summary || ''}</p>
              <div class="text-[11px] font-mono text-slate-400 break-all">Archivo: ${rv.deliverable_path || 'N/A'}</div>
              ${rv.source_url ? `<a href="${rv.source_url}" target="_blank" class="inline-block text-xs text-cyan-400 underline">Abrir enlace origen ↗</a>` : ''}
              ${d.authorized ? `
              <div class="grid grid-cols-3 gap-2 pt-2">
                <button onclick="decideReview('${rv.id}', 'approved')" class="py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">✅ Aprobar</button>
                <button onclick="decideReview('${rv.id}', 'changes_requested')" class="py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold">✏️ Corregir</button>
                <button onclick="decideReview('${rv.id}', 'rejected')" class="py-2 rounded-xl bg-rose-700 hover:bg-rose-600 text-white text-xs font-bold">🗑️ Descartar</button>
              </div>` : `<div class="text-[11px] text-amber-300 pt-1">Abre el panel desde el enlace de Discord para habilitar botones de aprobación.</div>`}
            </div>
          `).join("");
        }

        // Motores
        const opps = d.top_opportunities || [];
        document.getElementById("ghCount").textContent = `${opps.length} en cola`;
        document.getElementById("ghList").innerHTML = opps.length ? opps.map(o => `
          <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800 flex items-center justify-between gap-2">
            <div class="min-w-0">
              <div class="font-bold text-white truncate">${o.title}</div>
              <div class="text-[11px] text-slate-400 font-mono">${o.source} • Nivel ${o.difficulty}</div>
            </div>
            <a href="${o.url}" target="_blank" class="shrink-0 px-2.5 py-1 rounded-lg bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold">$${o.estimated_value_usd} ↗</a>
          </div>
        `).join("") : `<div class="text-slate-400">Escaneando nuevos bounties...</div>`;

        const actors = d.apify_actors || [];
        document.getElementById("apifyList").innerHTML = actors.length ? actors.map(a => `
          <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800 flex items-center justify-between gap-2">
            <div>
              <div class="font-bold text-white">${a.title}</div>
              <div class="text-[11px] text-slate-400 font-mono">${a.status_note} • ${a.pricing_model}</div>
            </div>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold ${a.healthy ? 'bg-emerald-950 text-emerald-300' : 'bg-rose-950 text-rose-300'}">${a.healthy ? 'ONLINE' : 'CHECK'}</span>
          </div>
        `).join("") : `<div class="text-slate-400">Inicializando fábrica de Actors...</div>`;

        const x4 = d.x402 || {};
        document.getElementById("x402Sales").textContent = `${x4.total_calls_paid || 0} ventas ($${x4.total_usd_earned || 0})`;
        document.getElementById("tunnelBox").textContent = d.public_url ? `${d.public_url}/api/v1/x402/scrape?url=https://example.com` : "Túnel local activo en 127.0.0.1:8080";
      } catch (e) {
        console.error(e);
      }
    }

    refreshAll();
    setInterval(refreshAll, 8000);
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def _is_owner_authorized(self) -> bool:
        client_ip = self.client_address[0]
        # Si entra directo sin proxy CF desde localhost, es el propio PC
        if client_ip in ("127.0.0.1", "::1") and not self.headers.get("CF-Connecting-IP"):
            return True
        qs = parse_qs(urlparse(self.path).query)
        token = qs.get("auth", [""])[0] or self.headers.get("X-AME-Auth", "")
        return hmac.compare_digest(token, MOBILE_TOKEN)

    def _send_json(self, code: int, payload: dict, extra_headers: dict = None):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-PAYMENT, PAYMENT-SIGNATURE, X-Payment-Tx, X-AME-Auth, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        qs = parse_qs(parsed.query)

        if route in ("/", "/index.html", "/mobile"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(MOBILE_APP_HTML.encode("utf-8"))
            return

        if route == "/.well-known/agent.json":
            pub = get_public_tunnel_url() or f"http://127.0.0.1:{PORT}"
            self._send_json(200, {
                "name": "Autonomous Micro-Entrepreneur (AME v3)",
                "version": "3.0.0",
                "network": "base",
                "chainId": 8453,
                "payee": USER_PAYOUT_WALLET,
                "standards": ["x402", "ERC-8021", "AIP-1"],
                "endpoints": {
                    "pricing": f"{pub}/api/v1/x402/pricing",
                    "scrape": f"{pub}/api/v1/x402/scrape",
                    "intel": f"{pub}/api/v1/x402/intel",
                    "solve": f"{pub}/api/v1/x402/solve",
                    "openapi": f"{pub}/openapi.json"
                }
            })
            return

        if route in ("/openapi.json", "/.well-known/ai-plugin.json"):
            pub = get_public_tunnel_url() or f"http://127.0.0.1:{PORT}"
            self._send_json(200, {
                "openapi": "3.0.1",
                "info": {"title": "AME v3 Residential Web Extraction & Base L2 x402 API", "version": "3.0.0"},
                "servers": [{"url": pub}],
                "paths": {
                    "/api/v1/x402/scrape": {"get": {"summary": "Clean anti-bot Markdown extraction via residential IP (x402 USDC/ETH)"}},
                    "/api/v1/x402/intel": {"get": {"summary": "Curated Base L2 DeFi yields & developer bounties (x402 USDC/ETH)"}},
                    "/api/v1/x402/solve": {"post": {"summary": "Autonomous code & smart contract analysis (x402 USDC/ETH)"}}
                }
            })
            return

        if route in ("/poidh-tx-dashboard", "/poidh-tx-dashboard.html"):
            html_p = BASE_DIR / "docs" / "poidh_txs_dashboard.html"
            self.send_response(200 if html_p.exists() else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_p.read_bytes() if html_p.exists() else b"Not found")
            return

        if route == "/poidh_daily_txs.json":
            json_p = BASE_DIR / "docs" / "poidh_daily_txs.json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json_p.read_bytes() if json_p.exists() else b"{}")
            return

        if route == "/api/status":
            auth = self._is_owner_authorized()
            gw = get_gateway()
            q_items = load_queue()
            viable_pending = [
                {
                    "id": x.get("id"),
                    "source": x.get("source"),
                    "title": x.get("title"),
                    "url": x.get("url"),
                    "difficulty": x.get("difficulty"),
                    "estimated_value_usd": x.get("estimated_value_usd")
                }
                for x in q_items if x.get("status") == "pending" and score_opportunity_cost_benefit(x) > 0
            ][:12]

            pending_revs = [x for x in load_reviews() if x.get("status") == "pending_review"]
            if not auth:
                # Ocultar rutas internas si un visitante sin clave consulta /api/status
                pending_revs = [{"id": r["id"], "category": r["category"], "title": r["title"], "reward_display": r["reward_display"], "summary": "Autentícate desde Discord para revisar detalles."} for r in pending_revs]

            with data_lock:
                fin = dict(telemetry_data["finance"])
                hw = dict(telemetry_data["hardware"])
                gpu = dict(telemetry_data["gpu"])
                br = dict(telemetry_data["active_brain"])

            self._send_json(200, {
                "authorized": auth,
                "finance": fin,
                "deepseek": get_deepseek_real_balance(),
                "gemini": get_gemini_status(),
                "active_brain": br,
                "hardware": hw,
                "gpu": gpu,
                "watchdog": get_watchdog_health(),
                "queue_summary": get_queue_summary(),
                "pending_reviews": pending_revs,
                "top_opportunities": viable_pending,
                "apify_actors": get_apify_actors(),
                "x402": gw.get_sales_stats(),
                "public_url": get_public_tunnel_url(),
                "server_time": time.strftime("%H:%M:%S")
            })
            return

        if route == "/api/v1/x402/pricing":
            self._send_json(200, {
                "x402Version": 1,
                "network": "base",
                "chainId": 8453,
                "payee": USER_PAYOUT_WALLET,
                "pricing": PRICING_TABLE
            })
            return

        if route == "/api/v1/x402/scrape":
            gw = get_gateway()
            tx_hash = gw.extract_tx_hash_from_headers(self.headers)
            target_url = qs.get("url", [""])[0]
            if not tx_hash:
                ch = gw.get_payment_challenge("scrape", self.path)
                self._send_json(402, ch, {"WWW-Authenticate": 'x402 network="base"'})
                return
            if not target_url:
                self._send_json(400, {"error": "Parámetro ?url=https://... requerido antes de consumir pago."})
                return
            ok_url, reason = extract_clean_webpage(target_url), "OK"
            if ok_url.get("status") == "error":
                self._send_json(400, ok_url)
                return
            ok, msg, meta = gw.verify_payment_tx(tx_hash, "scrape")
            if not ok:
                self._send_json(402, {"error": msg})
                return
            self._send_json(200, {"payment": meta, **ok_url})
            return

        if route == "/api/v1/x402/intel":
            gw = get_gateway()
            tx_hash = gw.extract_tx_hash_from_headers(self.headers)
            if not tx_hash:
                ch = gw.get_payment_challenge("intel", self.path)
                self._send_json(402, ch, {"WWW-Authenticate": 'x402 network="base"'})
                return
            ok, msg, meta = gw.verify_payment_tx(tx_hash, "intel")
            if not ok:
                self._send_json(402, {"error": msg})
                return
            topic = qs.get("topic", ["all"])[0].lower()
            payload = {"status": "success", "topic": topic, "payment": meta}
            if topic in ("defi", "yields", "all"):
                payload["defi_overview"] = get_base_defi_overview()
            if topic in ("bounties", "all"):
                payload["bounties"] = [x for x in load_queue() if x.get("status") == "pending"][:15]
            self._send_json(200, payload)
            return

        # Rutas auxiliares DeFi / DEX / AgentKit / EAS / Treasury
        if route == "/api/v1/agentkit/action":
            action = qs.get("action", [""])[0]
            params = {k: v[0] for k, v in qs.items() if k != "action"}
            self._send_json(200, get_agentkit_provider().dispatch_action(action, params))
            return
        if route == "/api/v1/defi/overview":
            self._send_json(200, get_base_defi_overview())
            return
        if route == "/api/v1/defi/yields":
            limit = int(qs.get("limit", [10])[0])
            min_tvl = float(qs.get("min_tvl", [500000])[0])
            sym = qs.get("symbol", [None])[0]
            stable = qs.get("stable", ["false"])[0].lower() in ("true", "1")
            res = get_base_top_yields(min_tvl=min_tvl, symbol_filter=sym, stable_only=stable, limit=limit)
            self._send_json(200, {"count": len(res), "yields": res})
            return
        if route == "/api/v1/dex/trending":
            res = get_base_trending_pools(min_liquidity_usd=float(qs.get("min_liquidity", [50000])[0]), limit=int(qs.get("limit", [10])[0]))
            self._send_json(200, {"count": len(res), "trending_pools": res})
            return
        if route == "/api/v1/treasury/status":
            self._send_json(200, get_treasury_status())
            return

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        route = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw_body)
        except Exception:
            body = {}

        if route == "/api/v1/reviews/decide":
            if not self._is_owner_authorized():
                self._send_json(403, {"error": "No autorizado. Abre el enlace privado desde Discord."})
                return
            rev_id = body.get("id", "")
            decision = body.get("decision", "")
            feedback = body.get("feedback", "")
            rev = get_review_by_id(rev_id)
            if not rev:
                self._send_json(404, {"error": "Elemento no encontrado"})
                return

            if decision == "approved" and rev.get("category") == "poidh_claim":
                ap = rev.get("action_payload") or {}
                if ap.get("bounty_id") and ap.get("proof_uri"):
                    ok, note = submit_approved_poidh_claim(
                        int(ap["bounty_id"]), rev["title"], ap.get("description", rev["summary"]), ap["proof_uri"], rev.get("opp_id", "")
                    )
                    update_review_decision(rev_id, "sent" if ok else "pending_review", result_note=note)
                    self._send_json(200, {"status": "ok" if ok else "error", "message": f"TX Base: {note}" if ok else note})
                    return

            update_review_decision(rev_id, decision, feedback=feedback)
            self._send_json(200, {"status": "ok", "message": f"Estado actualizado a: {decision}"})
            return

        if route == "/api/v1/x402/solve":
            gw = get_gateway()
            tx_hash = gw.extract_tx_hash_from_headers(self.headers)
            if not tx_hash:
                ch = gw.get_payment_challenge("solve", self.path)
                self._send_json(402, ch, {"WWW-Authenticate": 'x402 network="base"'})
                return
            ok, msg, meta = gw.verify_payment_tx(tx_hash, "solve")
            if not ok:
                self._send_json(402, {"error": msg})
                return
            prompt = body.get("prompt") or raw_body or "Analizar estado on-chain"
            res = route_task("code", prompt[:4000], difficulty=5, system_prompt="Agente x402 resolviendo petición comercial.")
            self._send_json(200, {"status": "success", "payment": meta, "solution": res})
            return

        self._send_json(404, {"error": "Not Found"})

    def log_message(self, format, *args):
        return


def run_server():
    threading.Thread(target=background_collector, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"[Dashboard v3] Mobile-First Command Center activo en http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
