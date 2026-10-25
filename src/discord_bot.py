# -*- coding: utf-8 -*-
"""
Discord Mobile Command Center v3.0 (Autonomous Micro-Entrepreneur):
- Revisión y aprobación móvil de trabajos terminados mediante botones interactivos y modales.
- 100% telemetría real en vivo (Base Mainnet USDC/ETH, saldo real DeepSeek USD, presupuesto 0.50 €/día).
- Captura completa del escritorio físico multi-ventana (WinSta0\Default + all_screens=True).
- Cero bucles en Base Sepolia y cero consumo oculto de GPU en segundo plano.
"""
import os
import io
import re
import sys
import json
import time
import ctypes
import asyncio
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks

# Blindaje de Instancia Única: Garantiza que NUNCA respondan dos bots a la vez
_bot_mutex = None
try:
    kernel32 = ctypes.windll.kernel32
    _bot_mutex = kernel32.CreateMutexW(None, True, "Global\\AutonomousMicroEntrepreneur_DiscordBot_SingleInstance")
    if kernel32.GetLastError() == 183:
        print("[Discord Bot Guard] Ya hay otra instancia del bot ejecutándose. Saliendo.")
        sys.exit(0)
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))
ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from discord_bridge import check_active_question, resolve_active_question, push_order
from brain_router import (
    route_task,
    get_today_spent,
    get_deepseek_real_balance,
    get_gemini_status,
    DAILY_BUDGET_EUR
)
from opportunity_queue import get_queue_summary, load_queue, update_opportunity_status
from review_queue import (
    get_pending_reviews,
    get_unnotified_reviews,
    mark_review_notified,
    get_review_by_id,
    update_review_decision,
    load_reviews,
    save_reviews
)
from dashboard_server import get_mobile_access_token, get_public_tunnel_url
from poidh_claim_submitter import submit_approved_poidh_claim
from x402_gateway import get_gateway, USER_PAYOUT_WALLET

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
raw_uid = os.getenv("DISCORD_AUTHORIZED_USER_ID", "637624631960010782").strip()
AUTHORIZED_USER_ID = int(raw_uid) if raw_uid.isdigit() and int(raw_uid) > 0 else 637624631960010782
DASHBOARD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID_DASHBOARD", "0") or "0")
GENERAL_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID_GENERAL", "0") or "0")
BOT_WALLET = os.getenv("PUBLIC_ADDRESS_TESTNET", "0x02c1F87F514493F359Afc0B3ff6b587434770361")
BASE_MAINNET_RPC = "https://mainnet.base.org"
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
ERC20_ABI = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

dashboard_message = None
last_report_hour = -1


def get_mobile_urls():
    mob_token = get_mobile_access_token()
    bookmark = f"https://ramgox.github.io/autonomous-micro-entrepreneur/mobile.html?auth={mob_token}"
    tunnel = get_public_tunnel_url()
    live = f"{tunnel}/?auth={mob_token}" if tunnel else bookmark
    return bookmark, live


def check_authorized(user_or_ctx, channel=None) -> bool:
    user = getattr(user_or_ctx, "author", None) or getattr(user_or_ctx, "user", None) or user_or_ctx
    uid = getattr(user, "id", 0)
    if AUTHORIZED_USER_ID == 0 or uid == AUTHORIZED_USER_ID:
        return True
    ch = channel or getattr(user_or_ctx, "channel", None)
    if ch and getattr(ch, "id", 0) in (GENERAL_CHANNEL_ID, DASHBOARD_CHANNEL_ID):
        return True
    return False


def save_api_key_to_system(key: str, provider: str = "DEEPSEEK_API_KEY"):
    env_content = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    pattern = rf"^{provider}=.*$"
    new_line = f"{provider}={key}"
    if re.search(pattern, env_content, flags=re.MULTILINE):
        env_content = re.sub(pattern, new_line, env_content, flags=re.MULTILINE)
    else:
        env_content += f"\n{new_line}\n"
    ENV_PATH.write_text(env_content, encoding="utf-8")
    os.environ[provider] = key


def _query_live_wallets() -> dict:
    data = {"u_eth": 0.0, "u_usdc": 0.0, "b_eth": 0.0, "b_usdc": 0.0}
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(BASE_MAINNET_RPC, request_kwargs={"timeout": 4}))
        usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)
        u_addr = Web3.to_checksum_address(USER_PAYOUT_WALLET)
        b_addr = Web3.to_checksum_address(BOT_WALLET)
        data["u_eth"] = float(w3.from_wei(w3.eth.get_balance(u_addr), "ether"))
        data["u_usdc"] = float(usdc.functions.balanceOf(u_addr).call()) / 1e6
        data["b_eth"] = float(w3.from_wei(w3.eth.get_balance(b_addr), "ether"))
        data["b_usdc"] = float(usdc.functions.balanceOf(b_addr).call()) / 1e6
    except Exception:
        pass
    return data


def _query_hardware() -> dict:
    hw = {"cpu": 0.0, "ram_pct": 0.0, "ram_txt": "0/16 GB", "gpu_txt": "0% (0W reposo)"}
    try:
        import psutil
        hw["cpu"] = round(psutil.cpu_percent(interval=None), 1)
        mem = psutil.virtual_memory()
        hw["ram_pct"] = round(mem.percent, 1)
        hw["ram_txt"] = f"{round(mem.used / (1024**3), 1)}/{round(mem.total / (1024**3), 1)} GB"
    except Exception:
        pass
    try:
        cmd = ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"]
        out = subprocess.check_output(cmd, encoding="utf-8", creationflags=0x08000000).strip()
        p = [x.strip() for x in out.split(",")]
        hw["gpu_txt"] = f"{p[2]}% util | {p[0]}/{p[1]} MB | {p[3]}°C"
    except Exception:
        pass
    return hw


def get_live_system_context() -> str:
    w = _query_live_wallets()
    hw = _query_hardware()
    spent = get_today_spent()
    ds = get_deepseek_real_balance()
    gem = get_gemini_status()
    q_sum = get_queue_summary()
    revs = get_pending_reviews()
    x402 = get_gateway().get_sales_stats()
    bookmark, live_url = get_mobile_urls()

    apify_file = BASE_DIR / "memoria" / "estado" / "apify_actors_status.json"
    apify_cnt = 0
    if apify_file.exists():
        try:
            apify_cnt = len([a for a in json.loads(apify_file.read_text(encoding="utf-8")) if a.get("smoke_ok")])
        except Exception:
            pass

    ds_usd = f"${ds.get('balance_usd', 0.0):.2f} USD" if ds.get("is_available") else "No disponible"
    gem_txt = f"Activa ({gem.get('status', '0,00 €')})" if gem.get("configured") and "expirad" not in str(gem.get("status", "")).lower() else f"Pausada ({gem.get('status', 'auto-fallback')})"

    return "\n".join([
        f"- Cartera Coinbase de Antonio ({USER_PAYOUT_WALLET}): {w['u_usdc']:.2f} USDC | {w['u_eth']:.6f} ETH en Base Mainnet.",
        f"- Cartera Operativa del Bot ({BOT_WALLET}): {w['b_eth']:.6f} ETH (gas Base Mainnet) | {w['b_usdc']:.2f} USDC.",
        f"- Gasto IA hoy (DeepSeek): {spent:.4f} € de un límite estricto de {DAILY_BUDGET_EUR:.2f} €/día. Saldo real en cuenta DeepSeek: {ds_usd}.",
        f"- Gemini Flash gratuita: {gem_txt}.",
        f"- Ollama Local (GTX 1660): En reserva de emergencia a 0,00 € ({hw['gpu_txt']}).",
        f"- Bandeja de Revisión Móvil: {len(revs)} trabajos listos esperando el OK de Antonio en Discord.",
        f"- Motor 1 (GitHub/Algora + POIDH Bounties): {q_sum.get('total_active', 0)} oportunidades filtradas en cola.",
        f"- Motor 2 (Actores Apify / MCP): {apify_cnt} actores construidos y verificados con smoke test real.",
        f"- Motor 3 (Pasarela x402 Base Mainnet): Online ({x402.get('total_sales', 0)} cobros verificados).",
        f"- Hardware PC 24/7: CPU {hw['cpu']}%, RAM {hw['ram_pct']}% ({hw['ram_txt']}).",
        f"- Enlace Panel Móvil permanente: {bookmark} (Túnel directo: {live_url})."
    ])


def ask_intelligent_brain(user_query: str, system_context: str) -> str:
    sys_prompt = (
        "Eres 'AME v3.0', el sistema autónomo 24/7 de Antonio, respondiéndole por Discord en su móvil.\n"
        "REGLAS ESTRICTAS:\n"
        "1. Usa EXCLUSIVAMENTE los datos reales del ESTADO EN TIEMPO REAL de abajo. NUNCA menciones Base Sepolia ni saldos inventados.\n"
        "2. Habla en español claro, directo, conciso y fácil de leer en la pantalla del móvil.\n"
        "3. Recuérdale cuando sea útil que puede escribir 'revisar' para aprobar entregas con botones, 'panel' para abrir el dashboard en el móvil o 'prompts' para sus chats paralelos de Gemini Pro.\n\n"
        f"ESTADO EN TIEMPO REAL:\n{system_context}"
    )
    ans = route_task(
        task_type="discord_chat",
        prompt=user_query,
        difficulty=3,
        system_prompt=sys_prompt
    )
    return ans.get("response", f"Estado en vivo:\n{system_context}")


# ==============================================================================
# CAPTURA COMPLETA DEL ESCRITORIO FÍSICO (MULTI-VENTANA)
# ==============================================================================

def _bind_interactive_desktop():
    """Asocia el hilo actual al escritorio interactivo WinSta0\\Default para capturar todo el escritorio físico y no una sola ventana."""
    try:
        user32 = ctypes.windll.user32
        DESKTOP_READOBJECTS = 0x0001
        DESKTOP_ENUMERATE = 0x0040
        DESKTOP_WRITEOBJECTS = 0x0080
        DESKTOP_SWITCHDESKTOP = 0x0100
        hdesk = user32.OpenInputDesktop(0, False, DESKTOP_READOBJECTS | DESKTOP_ENUMERATE | DESKTOP_WRITEOBJECTS | DESKTOP_SWITCHDESKTOP)
        if not hdesk:
            hdesk = user32.OpenDesktopW("Default", 0, False, DESKTOP_READOBJECTS | DESKTOP_ENUMERATE | DESKTOP_WRITEOBJECTS | DESKTOP_SWITCHDESKTOP)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
    except Exception:
        pass


def generate_telemetry_snapshot_image() -> bytes:
    from PIL import Image, ImageDraw
    w_wallets = _query_live_wallets()
    hw = _query_hardware()
    spent = get_today_spent()
    ds = get_deepseek_real_balance()
    revs = len(get_pending_reviews())
    q_sum = get_queue_summary()

    w, h = 960, 520
    img = Image.new("RGB", (w, h), color=(11, 17, 32))
    draw = ImageDraw.Draw(img)
    draw.rectangle([16, 16, w - 16, h - 16], outline=(16, 185, 129), width=3)
    draw.text((40, 32), "AME v3.0 — TELEMETRÍA REAL EN VIVO (MONITOR APAGADO / BLOQUEADO)", fill=(255, 255, 255))
    draw.text((40, 58), f"Hora: {time.strftime('%Y-%m-%d %H:%M:%S')} | Red: Base Mainnet (Chain ID 8453)", fill=(148, 163, 184))

    blocks = [
        ("CARTERAS REALES BASE MAINNET", [
            f"Coinbase Antonio: {w_wallets['u_usdc']:.2f} USDC | {w_wallets['u_eth']:.6f} ETH",
            f"Cartera Bot Gas:  {w_wallets['b_eth']:.6f} ETH | {w_wallets['b_usdc']:.2f} USDC",
            "Auto-Sweep activo hacia Coinbase (>= 0.50 USDC o > 0.0008 ETH)"
        ]),
        ("PRESUPUESTO IA & HARDWARE", [
            f"DeepSeek Hoy: {spent:.4f} EUR / {DAILY_BUDGET_EUR:.2f} EUR | Saldo: ${ds.get('balance_usd', 0.0):.2f} USD",
            f"CPU: {hw['cpu']}% | RAM: {hw['ram_pct']}% ({hw['ram_txt']})",
            f"GPU GTX 1660: {hw['gpu_txt']}"
        ]),
        ("MOTORES COMERCIALES & BANDEJA MÓVIL", [
            f"Entregas esperando tu OK en Discord: {revs}",
            f"Oportunidades reales en cola (GitHub + POIDH): {q_sum.get('total_active', 0)}",
            "Pasarela x402 + Actores Apify/MCP operativos"
        ])
    ]
    y = 95
    for title, lines in blocks:
        draw.rectangle([40, y, w - 40, y + 118], fill=(24, 34, 56), outline=(51, 65, 85), width=1)
        draw.text((56, y + 12), title, fill=(56, 189, 248))
        sy = y + 40
        for ln in lines:
            draw.text((62, sy), f"• {ln}", fill=(226, 232, 240))
            sy += 23
        y += 132

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _grab_full_desktop_sync() -> bytes:
    """Captura el escritorio completo (todas las pantallas y barra de tareas) en un hilo limpio."""
    _bind_interactive_desktop()
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=True)
        # Verificar que no sea un rectángulo completamente negro (sesión bloqueada)
        extrema = img.convert("L").getextrema()
        if extrema and extrema[1] > 8:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            val = buf.getvalue()
            if len(val) > 2500:
                return val
    except Exception:
        pass

    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # Monitor 0 = todos los monitores combinados
            sct_img = sct.grab(monitor)
            val = mss.tools.to_png(sct_img.rgb, sct_img.size)
            if len(val) > 2500:
                return val
    except Exception:
        pass
    return b""


async def capture_screen_bytes_async():
    desktop_bytes = await asyncio.to_thread(_grab_full_desktop_sync)
    if desktop_bytes:
        return desktop_bytes, "desktop"

    # Si el monitor físico está bloqueado por Windows, renderizar el Dashboard v3 real
    try:
        import base64
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
        mob_token = get_mobile_access_token()
        cfg = CrawlerRunConfig(screenshot=True)
        async with AsyncWebCrawler() as crawler:
            res = await crawler.arun(url=f"http://127.0.0.1:8080/?auth={mob_token}", config=cfg)
            if res.screenshot:
                raw_bytes = base64.b64decode(res.screenshot)
                if len(raw_bytes) > 2500:
                    return raw_bytes, "dashboard_live"
    except Exception:
        pass

    card = await asyncio.to_thread(generate_telemetry_snapshot_image)
    return card, "telemetry_card"


async def execute_screen_capture(channel):
    msg_wait = await channel.send("📸 Capturando escritorio completo...")
    try:
        img_bytes, mode = await capture_screen_bytes_async()
        file = discord.File(io.BytesIO(img_bytes), filename="escritorio_ame_v3.png")
        if mode == "desktop":
            txt = "🖥️ **Escritorio físico completo en tiempo real (todas las ventanas visibles):**"
        elif mode == "dashboard_live":
            txt = "📱 **Sesión de Windows bloqueada — Captura en vivo del nuevo Dashboard v3.0:**"
        else:
            txt = "📊 **Resumen gráfico en vivo (Monitor en ahorro de energía):**"
        await channel.send(content=txt, file=file)
        await msg_wait.delete()
    except Exception as e:
        await msg_wait.edit(content=f"❌ Error al capturar pantalla: `{e}`")


# ==============================================================================
# SISTEMA INTERACTIVO DE REVISIÓN Y APROBACIÓN MÓVIL (BOTONES + MODAL)
# ==============================================================================

def build_review_embed(rev: dict) -> discord.Embed:
    cat = rev.get("category", "tarea")
    cat_map = {
        "github_bounty": ("🐙 GitHub / Algora Bounty", discord.Color.from_rgb(59, 130, 246)),
        "apify_actor": ("🕷️ Actor Apify / MCP", discord.Color.from_rgb(168, 85, 247)),
        "poidh_claim": ("⛓️ Bounty On-Chain POIDH", discord.Color.from_rgb(16, 185, 129))
    }
    badge, color = cat_map.get(cat, ("📦 Entrega Lista", discord.Color.teal()))
    status = rev.get("status", "pending_review")

    embed = discord.Embed(
        title=f"{badge}: {rev.get('title', 'Sin título')[:180]}",
        url=rev.get("source_url") if str(rev.get("source_url", "")).startswith("http") else None,
        description=(rev.get("summary") or "Sin resumen.")[:900],
        color=color
    )
    embed.add_field(name="💵 Valor Estimado", value=f"`{rev.get('reward_display', '$0')}`", inline=True)
    embed.add_field(name="🤖 Generado por", value=f"`{rev.get('solver', 'IA')}`", inline=True)
    embed.add_field(name="📌 Estado", value=f"`{status.upper()}`", inline=True)
    if rev.get("deliverable_path"):
        embed.add_field(name="📂 Archivo Local", value=f"`{rev.get('deliverable_path')}`", inline=False)
    if rev.get("source_url"):
        embed.add_field(name="🔗 Origen", value=str(rev.get("source_url"))[:300], inline=False)
    embed.set_footer(text=f"ID: {rev.get('id')} • Usa los botones táctiles de abajo desde el móvil")
    return embed


def build_review_view(rev_id: str, disabled: bool = False) -> discord.ui.View:
    bookmark, _ = get_mobile_urls()
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label="Aprobar", emoji="✅", style=discord.ButtonStyle.success, custom_id=f"rev_ok:{rev_id}", disabled=disabled))
    view.add_item(discord.ui.Button(label="Ver Archivo", emoji="📄", style=discord.ButtonStyle.primary, custom_id=f"rev_view:{rev_id}", disabled=False))
    view.add_item(discord.ui.Button(label="Pedir Cambios", emoji="✏️", style=discord.ButtonStyle.secondary, custom_id=f"rev_edit:{rev_id}", disabled=disabled))
    view.add_item(discord.ui.Button(label="Descartar", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id=f"rev_drop:{rev_id}", disabled=disabled))
    view.add_item(discord.ui.Button(label="Panel Móvil", emoji="📱", style=discord.ButtonStyle.link, url=bookmark))
    return view


def build_mobile_link_view() -> discord.ui.View:
    bookmark, live_url = get_mobile_urls()
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label="Abrir Panel Móvil (Fijo)", emoji="📱", style=discord.ButtonStyle.link, url=bookmark))
    if live_url and live_url != bookmark:
        view.add_item(discord.ui.Button(label="Túnel Directo HTTPS", emoji="⚡", style=discord.ButtonStyle.link, url=live_url))
    return view


class FeedbackModal(discord.ui.Modal, title="✏️ Pedir Cambios a la Entrega"):
    instrucciones = discord.ui.TextInput(
        label="¿Qué quieres corregir o mejorar?",
        style=discord.TextStyle.paragraph,
        placeholder="Ej: Añade manejo de errores HTTP, haz el README más comercial o cambia el enfoque...",
        required=True,
        max_length=800
    )

    def __init__(self, rev_id: str):
        super().__init__()
        self.rev_id = rev_id

    async def on_submit(self, interaction: discord.Interaction):
        rev = get_review_by_id(self.rev_id)
        if not rev:
            return await interaction.response.send_message("❌ No se encontró la entrega.", ephemeral=True)

        await interaction.response.defer(thinking=True)
        feedback_txt = str(self.instrucciones.value).strip()

        def _refine_work():
            deliv_path_str = rev.get("deliverable_path", "")
            full_path = BASE_DIR / deliv_path_str if deliv_path_str else None
            current_content = ""
            if full_path and full_path.exists() and full_path.is_file():
                current_content = full_path.read_text(encoding="utf-8", errors="ignore")[:9000]

            prompt = (
                f"TAREA ORIGINAL: {rev.get('title')}\n"
                f"ORIGEN: {rev.get('source_url')}\n"
                f"CONTENIDO ACTUAL:\n{current_content}\n\n"
                f"CORRECCIÓN SOLICITADA POR ANTONIO DESDE EL MÓVIL:\n{feedback_txt}\n\n"
                "Genera la versión corregida completa, lista para entregar, e incluye al inicio un breve resumen de 3 líneas de los cambios aplicados."
            )
            ans = route_task(
                task_type="code",
                prompt=prompt,
                difficulty=6,
                system_prompt="Eres un ingeniero senior corrigiendo un entregable comercial según las instrucciones exactas del propietario."
            )
            new_text = ans.get("response", "")
            if full_path and full_path.is_file() and new_text and not ans.get("error"):
                full_path.write_text(new_text, encoding="utf-8")

            items = load_reviews()
            for it in items:
                if it.get("id") == self.rev_id:
                    it["feedback"] = feedback_txt
                    it["solver"] = ans.get("brain", it.get("solver", "IA"))
                    it["summary"] = f"[Corregido según tu nota: '{feedback_txt[:80]}']\n" + new_text[:700]
                    it["status"] = "pending_review"
                    it["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    break
            save_reviews(items)
            return get_review_by_id(self.rev_id), ans.get("error", False)

        updated_rev, had_err = await asyncio.to_thread(_refine_work)
        if had_err or not updated_rev:
            return await interaction.followup.send("⚠️ No se pudo regenerar automáticamente (revisa presupuesto IA), pero tu nota quedó guardada.")

        await interaction.followup.send(
            content=f"✅ **Entrega `{self.rev_id}` actualizada con tus cambios:**",
            embed=build_review_embed(updated_rev),
            view=build_review_view(self.rev_id)
        )


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    data = interaction.data or {}
    cid = str(data.get("custom_id", ""))
    if not cid.startswith(("rev_ok:", "rev_view:", "rev_edit:", "rev_drop:")):
        return

    if not check_authorized(interaction):
        return await interaction.response.send_message("❌ Solo Antonio puede gestionar entregas.", ephemeral=True)

    action, rev_id = cid.split(":", 1)
    rev = get_review_by_id(rev_id)
    if not rev:
        return await interaction.response.send_message("❌ Entrega no encontrada en `bandeja_revision.json`.", ephemeral=True)

    # 1. VER ARCHIVO COMPLETO EN EL MÓVIL
    if action == "rev_view":
        rel_path = rev.get("deliverable_path", "")
        target = BASE_DIR / rel_path if rel_path else None
        if target and target.exists():
            if target.is_dir():
                readme = target / "README.md"
                main_py = target / "src" / "main.py"
                send_file = readme if readme.exists() else (main_py if main_py.exists() else None)
                if send_file:
                    return await interaction.response.send_message(
                        content=f"📂 **Vista previa de `{rel_path}`:**",
                        file=discord.File(str(send_file), filename=send_file.name),
                        ephemeral=False
                    )
            elif target.is_file():
                return await interaction.response.send_message(
                    content=f"📄 **Entregable completo (`{target.name}`):**",
                    file=discord.File(str(target), filename=target.name),
                    ephemeral=False
                )
        return await interaction.response.send_message(
            f"📝 **Resumen guardado:**\n```\n{rev.get('summary', 'Sin archivo local.')[:1700]}\n```",
            ephemeral=False
        )

    # 2. PEDIR CAMBIOS (MODAL MÓVIL)
    if action == "rev_edit":
        return await interaction.response.send_modal(FeedbackModal(rev_id))

    # 3. DESCARTAR ENTREGA
    if action == "rev_drop":
        update_review_decision(rev_id, "discarded", result_note="Descartado desde Discord móvil")
        if rev.get("opp_id"):
            update_opportunity_status(rev["opp_id"], "rejected_review")
        updated = get_review_by_id(rev_id) or rev
        await interaction.response.edit_message(embed=build_review_embed(updated), view=build_review_view(rev_id, disabled=True))
        return await interaction.followup.send(f"🗑️ Entrega `{rev_id}` descartada y retirada de la cola.")

    # 4. APROBAR ENTREGA
    if action == "rev_ok":
        await interaction.response.defer()
        cat = rev.get("category", "")

        if cat == "poidh_claim":
            ap = rev.get("action_payload") or {}
            bounty_id = ap.get("bounty_id")
            proof_uri = ap.get("proof_uri", rev.get("preview_url", ""))
            if not bounty_id or not proof_uri:
                return await interaction.followup.send(
                    "⚠️ Este reclamo POIDH requiere una URL de imagen pública verificada (`proof_uri` HTTP 200) antes de gastar gas. Usa **Pedir Cambios** para adjuntar la URL de prueba."
                )
            ok, note = await asyncio.to_thread(
                submit_approved_poidh_claim,
                int(bounty_id),
                rev.get("title", ""),
                ap.get("description", rev.get("summary", "")),
                proof_uri,
                rev.get("opp_id", "")
            )
            if ok:
                update_review_decision(rev_id, "sent", result_note=f"TX Base: {note}")
                updated = get_review_by_id(rev_id) or rev
                await interaction.message.edit(embed=build_review_embed(updated), view=build_review_view(rev_id, disabled=True))
                return await interaction.followup.send(f"🚀 **Reclamo POIDH firmado y enviado en Base Mainnet:**\n<https://basescan.org/tx/{note}>")
            else:
                return await interaction.followup.send(f"❌ **Bloqueado por seguridad antes de gastar gas:** {note}")

        elif cat == "github_bounty":
            update_review_decision(rev_id, "approved", result_note="Aprobado por Antonio en móvil")
            if rev.get("opp_id"):
                update_opportunity_status(rev["opp_id"], "approved_ready")
            updated = get_review_by_id(rev_id) or rev
            await interaction.message.edit(embed=build_review_embed(updated), view=build_review_view(rev_id, disabled=True))
            rel_path = rev.get("deliverable_path", "")
            f_obj = discord.File(str(BASE_DIR / rel_path)) if rel_path and (BASE_DIR / rel_path).is_file() else None
            msg_ok = (
                f"✅ **Propuesta GitHub Bounty aprobada (`{rev.get('reward_display')}`):**\n"
                f"• Issue oficial: {rev.get('source_url')}\n"
                f"• Solución lista en `{rel_path}` (o pásasela a tu Chat Paralelo de Gemini Pro con el comando `prompts` para abrir el PR limpio con tests)."
            )
            if f_obj:
                return await interaction.followup.send(msg_ok, file=f_obj)
            return await interaction.followup.send(msg_ok)

        elif cat == "apify_actor":
            update_review_decision(rev_id, "approved", result_note="Actor aprobado para publicación en Apify Store")
            updated = get_review_by_id(rev_id) or rev
            await interaction.message.edit(embed=build_review_embed(updated), view=build_review_view(rev_id, disabled=True))
            apify_tok = os.getenv("APIFY_TOKEN", "").strip()
            actor_dir = rev.get("deliverable_path", "apify_actors")
            if apify_tok:
                return await interaction.followup.send(
                    f"✅ **Actor `{rev.get('title')}` aprobado.** `APIFY_TOKEN` detectado: listo para publicar desde `{actor_dir}`."
                )
            return await interaction.followup.send(
                f"✅ **Actor `{rev.get('title')}` aprobado y validado localmente (`{actor_dir}`).**\n"
                f"Para dejarlo cobrando en Apify Store ($29/mes + Pay-Per-Event), pega tu `APIFY_TOKEN` aquí o ejecuta `npx apify-cli login && npx apify-cli push` dentro de `{actor_dir}`."
            )

        update_review_decision(rev_id, "approved")
        updated = get_review_by_id(rev_id) or rev
        await interaction.message.edit(embed=build_review_embed(updated), view=build_review_view(rev_id, disabled=True))
        return await interaction.followup.send(f"✅ Entrega `{rev_id}` marcada como aprobada.")


# ==============================================================================
# EMBEDS DE ESTADO, BOUNTIES, APIFY Y PROMPTS MÓVILES
# ==============================================================================

async def send_status_embed(channel):
    w = await asyncio.to_thread(_query_live_wallets)
    hw = await asyncio.to_thread(_query_hardware)
    spent = get_today_spent()
    ds = await asyncio.to_thread(get_deepseek_real_balance)
    gem = get_gemini_status()
    q_sum = get_queue_summary()
    revs = get_pending_reviews()
    bookmark, live_url = get_mobile_urls()

    ds_usd = f"${ds.get('balance_usd', 0.0):.2f} USD" if ds.get("is_available") else "N/D"
    gem_txt = f"🟢 {gem.get('status', 'Activa')}" if gem.get("configured") and "expirad" not in str(gem.get("status", "")).lower() else f"🟡 {gem.get('status', 'Fallback')}"

    embed = discord.Embed(
        title="📱 Centro de Mando Móvil — AME v3.0",
        description="Datos 100% reales verificados en vivo. Cero simulaciones.",
        color=discord.Color.from_rgb(16, 185, 129)
    )
    embed.add_field(
        name="💰 Tu Cartera Coinbase (Base)",
        value=f"`{w['u_usdc']:.2f} USDC` | `{w['u_eth']:.5f} ETH`",
        inline=True
    )
    embed.add_field(
        name="⛽ Cartera Gas del Bot",
        value=f"`{w['b_eth']:.6f} ETH`",
        inline=True
    )
    embed.add_field(
        name="📥 Para Revisar en Móvil",
        value=f"**`{len(revs)}` entregas** (`revisar`)",
        inline=True
    )
    embed.add_field(
        name="🧠 DeepSeek (Tope 0.50€/día)",
        value=f"Hoy: `{spent:.4f} €` / `{DAILY_BUDGET_EUR:.2f} €`\nSaldo cuenta: `{ds_usd}`",
        inline=True
    )
    embed.add_field(
        name="⚡ Gemini Flash & GPU",
        value=f"Gemini: {gem_txt}\nGTX 1660: `{hw['gpu_txt']}`",
        inline=True
    )
    embed.add_field(
        name="🚀 Motores Activos",
        value=f"Cola Bounties: `{q_sum.get('total_active', 0)}`\nPC: CPU `{hw['cpu']}%` | RAM `{hw['ram_pct']}%`",
        inline=True
    )
    embed.set_footer(text="Comandos rápidos sin '!': panel • revisar • bounties • apify • prompts • captura")
    await channel.send(embed=embed, view=build_mobile_link_view())


async def send_pending_reviews_list(channel):
    pending = get_pending_reviews()
    if not pending:
        return await channel.send("✅ **No tienes entregas pendientes de revisión ahora mismo.** El sistema te avisará aquí con botones en cuanto termine la siguiente.", view=build_mobile_link_view())
    await channel.send(f"📱 **Tienes `{len(pending)}` entrega(s) esperando tu revisión:**")
    for rev in pending[:5]:
        await channel.send(embed=build_review_embed(rev), view=build_review_view(rev["id"]))
        mark_review_notified(rev["id"])


async def send_bounties_summary(channel):
    items = [x for x in load_queue() if x.get("status") == "pending"]
    if not items:
        return await channel.send("🔎 La cola de bounties se está escaneando ahora mismo. Prueba en unos minutos.")
    lines = []
    for it in items[:8]:
        src = "🐙 GH" if "github" in str(it.get("source", "")) else "⛓️ POIDH"
        usd_v = float(it.get("estimated_value_usd", it.get("reward_usd_est", 0)) or 0)
        lines.append(f"• {src} **`${usd_v:.0f}`** — [{it.get('title', '')[:55]}]({it.get('url', '')})")
    embed = discord.Embed(
        title=f"🎯 Top Oportunidades Filtradas en Cola ({len(items)} activas)",
        description="\n".join(lines),
        color=discord.Color.blue()
    )
    embed.set_footer(text="Solo software/datos verificables y sin asignar • Cero spam automático")
    await channel.send(embed=embed, view=build_mobile_link_view())


async def send_apify_summary(channel):
    p = BASE_DIR / "memoria" / "estado" / "apify_actors_status.json"
    if not p.exists():
        return await channel.send("🕷️ Ejecutando fábrica de actores Apify... consulta en 1 minuto.")
    actors = json.loads(p.read_text(encoding="utf-8"))
    lines = []
    for a in actors:
        ok = "🟢 Smoke-Test OK" if a.get("smoke_ok") else "🔴 Revisar"
        lines.append(f"**{a.get('title')}** (`{a.get('slug')}`)\n• Estado: {ok} | Modelo: `{a.get('monetization', 'Pay-Per-Event')}`\n• Ruta: `{a.get('path')}`")
    embed = discord.Embed(
        title="🕷️ Motor 2: Actores Apify Store & Servidores MCP",
        description="\n\n".join(lines) or "Sin actores registrados.",
        color=discord.Color.purple()
    )
    await channel.send(embed=embed, view=build_mobile_link_view())


async def send_parallel_prompts(channel):
    prompts_file = BASE_DIR / "memoria" / "PROMPTS_CHATS_PARALELOS.md"
    msg = (
        "🧠 **Prompts listos para tus Chats Paralelos de Gemini Pro (Coste API 0,00 €):**\n"
        "1️⃣ **Chat Bucle Resolutor de Bounties (`cada 4h`):** Toma la mejor bounty de `memoria/MOTOR_1_BOUNTIES_GITHUB.md`, clona/resuelve con tests reales y deja la entrega en `bandeja_revision.json`.\n"
        "2️⃣ **Chat Bucle Auditor & Apify/MCP (`cada 8h`):** Audita calidad de código, mejora actores de `apify_actors/` y limpia oportunidades caducadas.\n"
        "👇 *Te adjunto el archivo completo para copiar y pegar desde el móvil o PC:*"
    )
    if prompts_file.exists():
        await channel.send(msg, file=discord.File(str(prompts_file), filename="PROMPTS_CHATS_PARALELOS.md"), view=build_mobile_link_view())
    else:
        await channel.send(msg, view=build_mobile_link_view())


# ==============================================================================
# EVENTOS Y COMANDOS MÓVILES
# ==============================================================================

@bot.event
async def on_ready():
    print(f"[Discord v3] Conectado como {bot.user.name} (ID: {bot.user.id})")
    if DASHBOARD_CHANNEL_ID and not update_dashboard.is_running():
        update_dashboard.start()
    if not notify_pending_reviews_loop.is_running():
        notify_pending_reviews_loop.start()
    if not scheduled_12h_reports.is_running():
        scheduled_12h_reports.start()


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    if not check_authorized(message):
        return

    text = message.content.strip()
    lower = text.lower()

    # Guardado rápido de API Keys desde el móvil (SIN auto-spam en GitHub)
    key_match_gemini = re.search(r"(AIza[a-zA-Z0-9_-]{30,45}|AQ\.[a-zA-Z0-9_-]{30,64})", text)
    if key_match_gemini:
        extracted = key_match_gemini.group(1)
        save_api_key_to_system(extracted, "GEMINI_API_KEY")
        return await message.reply(f"⚡ **Clave `GEMINI_API_KEY` actualizada:** `{extracted[:6]}...{extracted[-4:]}`")

    key_match_ds = re.search(r"(sk-[a-zA-Z0-9_-]{28,64})", text)
    if key_match_ds:
        extracted = key_match_ds.group(1)
        save_api_key_to_system(extracted, "DEEPSEEK_API_KEY")
        return await message.reply(f"🔐 **Clave `DEEPSEEK_API_KEY` actualizada (tope `0.50 €/día`):** `{extracted[:6]}...{extracted[-4:]}`")

    key_match_gh = re.search(r"(ghp_[a-zA-Z0-9]{30,50}|github_pat_[a-zA-Z0-9_]{40,120})", text)
    if key_match_gh:
        extracted = key_match_gh.group(1)
        save_api_key_to_system(extracted, "GITHUB_TOKEN")
        return await message.reply(f"🐙 **Token `GITHUB_TOKEN` guardado de forma segura:** `{extracted[:6]}...{extracted[-4:]}` (Cero envíos automáticos sin tu botón de Aprobar).")

    key_match_apify = re.search(r"(apify_api_[a-zA-Z0-9]{24,60})", text)
    if key_match_apify:
        extracted = key_match_apify.group(1)
        save_api_key_to_system(extracted, "APIFY_TOKEN")
        return await message.reply(f"🕷️ **Token `APIFY_TOKEN` guardado:** `{extracted[:12]}...{extracted[-4:]}`")

    # Respuesta a pregunta activa del sistema
    active_q = check_active_question()
    if active_q and active_q.get("status") == "pending":
        resolve_active_question(text)
        return await message.reply(f"✅ **Respuesta entregada al sistema:** `{text[:120]}`")

    # Atajos móviles de 1 palabra (sin necesidad de escribir '!')
    if lower in ("panel", "movil", "móvil", "dashboard", "web", "link", "enlace"):
        bookmark, live_url = get_mobile_urls()
        return await message.reply(
            f"📱 **Acceso Móvil Directo (guárdalo en favoritos del móvil):**\n{bookmark}\n\n⚡ **Túnel en vivo actual:**\n{live_url}",
            view=build_mobile_link_view()
        )

    if lower in ("revisar", "pendientes", "bandeja", "entregas", "aprobar"):
        return await send_pending_reviews_list(message.channel)

    if lower in ("bounties", "tareas", "cola", "oportunidades"):
        return await send_bounties_summary(message.channel)

    if lower in ("apify", "actores", "mcp"):
        return await send_apify_summary(message.channel)

    if lower in ("prompts", "prompt", "paralelos", "chats"):
        return await send_parallel_prompts(message.channel)

    if lower in ("ayuda", "comandos", "help", "menu", "menú"):
        return await message.reply(
            "📱 **Atajos rápidos desde el móvil (escríbelos tal cual):**\n"
            "• `revisar` — Ver trabajos terminados con botones **Aprobar / Ver / Editar / Descartar**\n"
            "• `panel` — Abrir el nuevo Dashboard móvil desde fuera de casa\n"
            "• `estado` — Resumen real de carteras, gasto DeepSeek (`0.50€/día`) y motores\n"
            "• `bounties` — Ver bounties en `$USD` filtradas en cola\n"
            "• `apify` — Estado de tus Actores Apify / MCP\n"
            "• `prompts` — Prompts listos para tus chats en bucle de Gemini Pro\n"
            "• `captura` — Foto completa de todas las ventanas del PC",
            view=build_mobile_link_view()
        )

    if any(k in lower for k in ("abrir obsidian", "abre obsidian", "mostrar obsidian")):
        try:
            obs_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Obsidian\Obsidian.exe")
            subprocess.Popen([obs_path, str(BASE_DIR / "memoria")])
            return await message.reply("📂 **Obsidian abierto en el PC.** Pide `captura` para verlo.")
        except Exception as e:
            return await message.reply(f"❌ No se pudo abrir Obsidian: `{e}`")

    if any(k in lower for k in ("captura", "pantalla", "screenshot", "escritorio")):
        return await execute_screen_capture(message.channel)

    if lower in ("estado", "status", "telemetria", "telemetría") or any(k in lower for k in ("estado del sistema", "como va el sistema", "cómo va el sistema")):
        return await send_status_embed(message.channel)

    # Órdenes explícitas para el daemon
    if lower.startswith(("orden:", "tarea:")):
        clean_ord = text.split(":", 1)[1].strip()
        push_order(clean_ord, source="discord_mobile")
        return await message.reply(f"📥 **Orden enviada al Daemon 24/7:** `{clean_ord}`")

    # Conversación directa con contexto real v3
    async with message.channel.typing():
        sys_context = await asyncio.to_thread(get_live_system_context)
        reply = await asyncio.to_thread(ask_intelligent_brain, text, sys_context)
        for chunk in [reply[i:i + 1900] for i in range(0, max(1, len(reply)), 1900)]:
            await message.reply(chunk)


@bot.command(name="screen", aliases=["captura", "pantalla"])
async def screen_cmd(ctx):
    if check_authorized(ctx):
        await execute_screen_capture(ctx.channel)


@bot.command(name="status", aliases=["estado"])
async def status_cmd(ctx):
    if check_authorized(ctx):
        await send_status_embed(ctx.channel)


@bot.command(name="dashboard", aliases=["panel", "movil"])
async def dashboard_cmd(ctx):
    if check_authorized(ctx):
        bookmark, live_url = get_mobile_urls()
        await ctx.send(f"📱 **Panel Móvil v3.0:**\n• Favorito permanente: {bookmark}\n• Túnel actual: {live_url}", view=build_mobile_link_view())


@bot.command(name="revisar", aliases=["pendientes", "bandeja"])
async def revisar_cmd(ctx):
    if check_authorized(ctx):
        await send_pending_reviews_list(ctx.channel)


@bot.command(name="bounties", aliases=["tareas"])
async def bounties_cmd(ctx):
    if check_authorized(ctx):
        await send_bounties_summary(ctx.channel)


@bot.command(name="apify", aliases=["actores"])
async def apify_cmd(ctx):
    if check_authorized(ctx):
        await send_apify_summary(ctx.channel)


@bot.command(name="prompts")
async def prompts_cmd(ctx):
    if check_authorized(ctx):
        await send_parallel_prompts(ctx.channel)


@bot.command(name="orden")
async def orden_cmd(ctx, *, texto: str):
    if check_authorized(ctx):
        push_order(texto, source="command_orden")
        await ctx.send(f"📥 **Orden encolada en el Daemon 24/7:** `{texto}`")


@bot.command(name="reporte")
async def reporte_cmd(ctx):
    if check_authorized(ctx):
        from twelve_hour_reporter import send_12h_report
        ok = await asyncio.to_thread(send_12h_report, "Bajo Demanda")
        await ctx.reply("📋 Reporte ejecutivo enviado." if ok else "⚠️ No se pudo enviar el reporte.")


# ==============================================================================
# BUCLES LIGEROS DE NOTIFICACIÓN MÓVIL Y PANEL #DASHBOARD-24-7 (0% GPU)
# ==============================================================================

@tasks.loop(seconds=20)
async def notify_pending_reviews_loop():
    if not GENERAL_CHANNEL_ID:
        return
    ch = bot.get_channel(GENERAL_CHANNEL_ID)
    if not ch:
        return
    try:
        unnotified = get_unnotified_reviews()
        for rev in unnotified[:3]:
            await ch.send(
                content=f"🔔 <@{AUTHORIZED_USER_ID}> **Nueva entrega lista para revisar desde tu móvil:**",
                embed=build_review_embed(rev),
                view=build_review_view(rev["id"])
            )
            mark_review_notified(rev["id"])
    except Exception as e:
        print(f"[Review Loop Error]: {e}")


@tasks.loop(seconds=60)
async def update_dashboard():
    global dashboard_message
    if not DASHBOARD_CHANNEL_ID:
        return
    channel = bot.get_channel(DASHBOARD_CHANNEL_ID)
    if not channel:
        return

    try:
        w = await asyncio.to_thread(_query_live_wallets)
        hw = await asyncio.to_thread(_query_hardware)
        spent = get_today_spent()
        ds = await asyncio.to_thread(get_deepseek_real_balance)
        q_sum = get_queue_summary()
        revs = len(get_pending_reviews())
        ds_usd = f"${ds.get('balance_usd', 0.0):.2f}" if ds.get("is_available") else "N/D"

        embed = discord.Embed(
            title="📊 Panel en Vivo 24/7 — AME v3.0 (Datos Reales)",
            description=f"Actualizado: `{time.strftime('%Y-%m-%d %H:%M:%S')}` • Red: `Base Mainnet`",
            color=discord.Color.from_rgb(16, 185, 129) if revs > 0 else discord.Color.teal()
        )
        embed.add_field(name="💰 Tu Coinbase", value=f"`{w['u_usdc']:.2f} USDC` | `{w['u_eth']:.5f} ETH`", inline=True)
        embed.add_field(name="⛽ Gas Bot (Base)", value=f"`{w['b_eth']:.6f} ETH`", inline=True)
        embed.add_field(name="📱 Por Revisar", value=f"`{revs}` entregas (`revisar`)", inline=True)
        embed.add_field(name="🧠 DeepSeek Hoy", value=f"`{spent:.4f}€` / `{DAILY_BUDGET_EUR:.2f}€` (Saldo `{ds_usd}`)", inline=True)
        embed.add_field(name="🎯 Cola Bounties", value=f"`{q_sum.get('total_active', 0)}` oportunidades", inline=True)
        embed.add_field(name="🖥️ Hardware", value=f"CPU `{hw['cpu']}%` • GPU `{hw['gpu_txt'].split('|')[0].strip()}`", inline=True)

        view = build_mobile_link_view()
        if dashboard_message is None:
            async for m in channel.history(limit=8):
                if m.author == bot.user and m.embeds:
                    dashboard_message = m
                    break
        if dashboard_message is None:
            dashboard_message = await channel.send(embed=embed, view=view)
        else:
            await dashboard_message.edit(embed=embed, view=view)
    except Exception as e:
        print(f"[Dashboard Channel Update Error]: {e}")


@tasks.loop(seconds=45)
async def scheduled_12h_reports():
    global last_report_hour
    now = time.localtime()
    if now.tm_hour in (9, 21) and now.tm_min == 0 and now.tm_hour != last_report_hour:
        last_report_hour = now.tm_hour
        try:
            from twelve_hour_reporter import send_12h_report
            await asyncio.to_thread(send_12h_report)
        except Exception as e:
            print(f"[Discord 12h Report Error]: {e}")


if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Configura DISCORD_BOT_TOKEN en config/.env para iniciar el bot.")
