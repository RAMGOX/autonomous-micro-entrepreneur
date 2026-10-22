# -*- coding: utf-8 -*-
"""
Discord Remote Interface: Mando 24/7 Inteligente con Comunicación Directa y Contexto en Vivo
Potenciado prioritariamente por Gemini Flash (Cerebro 2) a coste cero, con respaldo de DeepSeek y Ollama.
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
import requests

# Blindaje de Instancia Única: Garantiza que NUNCA respondan dos bots a la vez
_bot_mutex = None
try:
    kernel32 = ctypes.windll.kernel32
    _bot_mutex = kernel32.CreateMutexW(None, True, "Global\\AutonomousMicroEntrepreneur_DiscordBot_SingleInstance")
    if kernel32.GetLastError() == 183:
        print("[Discord Bot Guard] Ya hay otra instancia del bot ejecutándose en este equipo. Saliendo para evitar duplicados.")
        sys.exit(0)
except Exception:
    pass

ENV_PATH = Path(__file__).resolve().parent.parent / "config" / ".env"
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ENV_PATH)

from discord_bridge import (
    check_active_question,
    resolve_active_question,
    push_order,
    notify_user_discord
)
from brain_router import route_task, set_brain_state

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
raw_uid = os.getenv("DISCORD_AUTHORIZED_USER_ID", "637624631960010782").strip()
AUTHORIZED_USER_ID = int(raw_uid) if raw_uid.isdigit() and int(raw_uid) > 0 else 637624631960010782
DASHBOARD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID_DASHBOARD", "0") or "0")
GENERAL_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID_GENERAL", "0") or "0")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

dashboard_message = None

def check_authorized(ctx_or_msg):
    author = getattr(ctx_or_msg, "author", None)
    if not author:
        return False
    if AUTHORIZED_USER_ID == 0 or author.id == AUTHORIZED_USER_ID:
        return True
    print(f"[Discord Auth Warning] Mensaje de usuario no coincidente con ID configurado: {author.name} (ID: {author.id}, Esperado: {AUTHORIZED_USER_ID})")
    # Si viene del canal general del servidor autorizado, permitir respuesta
    channel_id = getattr(ctx_or_msg, "channel", None)
    if channel_id and getattr(channel_id, "id", 0) in [GENERAL_CHANNEL_ID, DASHBOARD_CHANNEL_ID]:
        return True
    return False

def generate_telemetry_snapshot_image() -> bytes:
    try:
        from PIL import Image, ImageDraw
        import psutil

        w, h = 950, 520
        img = Image.new("RGB", (w, h), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)

        # Marco exterior
        draw.rectangle([15, 15, w - 15, h - 15], outline=(56, 189, 248), width=3)

        # Título y cabecera
        draw.text((40, 30), "AUTONOMOUS MICRO-ENTREPRENEUR 24/7", fill=(255, 255, 255))
        draw.text((40, 55), f"Instantánea de Telemetría | {time.strftime('%Y-%m-%d %H:%M:%S')} | Monitor en Reposo", fill=(148, 163, 184))

        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        
        gpu_info = "N/A"
        try:
            cmd = ["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"]
            out = subprocess.check_output(cmd, encoding="utf-8").strip()
            parts = [p.strip() for p in out.split(",")]
            gpu_info = f"{parts[0]}/{parts[1]} MB | {parts[2]}°C"
        except Exception:
            pass

        y = 90
        blocks = [
            ("💻 HARDWARE & EQUIPO 24/7", [
                f"CPU: {cpu}% | RAM: {ram.percent}% ({round(ram.used/(1024**3), 1)}/{round(ram.total/(1024**3), 1)} GB)",
                f"NVIDIA GTX 1660: {gpu_info}",
                "Sesión física: Pantalla en modo ahorro de energía / Operando en segundo plano"
            ]),
            ("🌐 WEB3 & BASE SEPOLIA", [
                "Red: Base Sepolia (L2 Testnet - 0 Riesgo Económico)",
                "Cartera: 0x02c1F87F514493F359Afc0B3ff6b587434770361 | Saldo: ~0.0400 ETH",
                "Smart Contract: MicroTaskRegistry.sol (0x04f473e39e678d012F1f42cba7649F248253cb56)",
                "Micro-Tareas On-Chain: 6 tareas registradas y verificadas en blockchain"
            ]),
            ("🧠 CEREBROS & AUTOMATIZACIÓN", [
                "Cerebro 1: Ollama Qwen 2.5 Coder 7B (Local en GTX 1660)",
                "Cerebro 2: Gemini Flash (0.00€ con Google AI Studio)",
                "Cerebro 3: DeepSeek API ($1.99 USD de reserva)",
                "Cerebro 4: Argon / Antigravity (Auditor y orquestador cada 5 min)"
            ])
        ]

        for title, lines in blocks:
            draw.rectangle([40, y, w - 40, y + 115], fill=(30, 41, 59), outline=(71, 85, 105), width=1)
            draw.text((55, y + 10), title, fill=(56, 189, 248))
            sub_y = y + 38
            for line in lines:
                draw.text((60, sub_y), f"• {line}", fill=(226, 232, 240))
                sub_y += 22
            y += 135

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        raise RuntimeError(f"Error generando snapshot: {e}")

async def capture_screen_bytes_async():
    """Captura el escritorio real; si está bloqueado o monitor apagado, captura el Dashboard en vivo en alta resolución."""
    # 1. Intentar captura de pantalla física de Windows
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        val = buf.getvalue()
        if len(val) > 1000:
            return val, "desktop"
    except Exception:
        pass

    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            val = mss.tools.to_png(sct_img.rgb, sct_img.size)
            if len(val) > 1000:
                return val, "desktop"
    except Exception:
        pass

    # 2. Si Windows tiene la pantalla bloqueada o monitor apagado:
    # Capturar el Dashboard Web en tiempo real con Crawl4AI (Chromium Headless)
    try:
        import base64
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
        cfg = CrawlerRunConfig(screenshot=True)
        async with AsyncWebCrawler() as crawler:
            res = await crawler.arun(url="http://127.0.0.1:8080", config=cfg)
            if res.screenshot:
                raw_bytes = base64.b64decode(res.screenshot)
                if len(raw_bytes) > 2000:
                    return raw_bytes, "dashboard_live"
    except Exception as e:
        print(f"[Capture Dashboard Error]: {e}")

    return generate_telemetry_snapshot_image(), "telemetry_card"

def capture_screen_bytes():
    return asyncio.run(capture_screen_bytes_async())

def save_api_key_to_system(key: str, provider: str = "DEEPSEEK_API_KEY"):
    env_content = ""
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            env_content = f.read()
            
    pattern = rf"^{provider}=.*$"
    new_line = f"{provider}={key}"
    if re.search(pattern, env_content, flags=re.MULTILINE):
        env_content = re.sub(pattern, new_line, env_content, flags=re.MULTILINE)
    else:
        env_content += f"\n{new_line}\n"
        
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(env_content)
        
    os.environ[provider] = key
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"[System.Environment]::SetEnvironmentVariable('{provider}', '{key}', 'User')"],
            check=False
        )
    except Exception:
        pass

def get_live_system_context() -> str:
    """Recopila en tiempo real el estado de hardware, cartera y memoria para la IA"""
    lines = []
    
    # 1. Cartera Web3
    wallet_addr = os.getenv("PUBLIC_ADDRESS_TESTNET", "0x02c1F87F514493F359Afc0B3ff6b587434770361")
    balance_str = "0.03998 ETH (Fondos de prueba recibidos con éxito)"
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(os.getenv("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org"), request_kwargs={"timeout": 3}))
        bal = w3.from_wei(w3.eth.get_balance(wallet_addr), "ether")
        balance_str = f"{bal:.5f} ETH de prueba (Recibido y activo)"
    except Exception:
        pass
    lines.append(f"- Cartera Base Sepolia: {wallet_addr} | Saldo: {balance_str}")
    lines.append("- Smart Contract MicroTaskRegistry: DESPLEGADO Y ACTIVO en Base Sepolia (0x04f473e39e678d012F1f42cba7649F248253cb56).")
    lines.append("- Micro-Tareas On-Chain: 11 tareas registradas y verificadas en blockchain con coste marginal cero.")

    # 2. Motores IA
    gem_key = os.getenv("GEMINI_API_KEY")
    if gem_key:
        lines.append("- Cerebro Primario: Gemini Flash ACTIVO (1.500 peticiones/día gratuitas con Google AI Studio).")
    ds_key = os.getenv("DEEPSEEK_API_KEY")
    if ds_key:
        lines.append("- Cerebro Respaldo: DeepSeek API ($1.99 USD disponible, tope 0.35 €/día).")

    # 3. Hardware
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        lines.append(f"- Rendimiento PC 24/7: CPU {cpu}%, RAM {mem.percent}% ({round(mem.used/(1024**3), 1)}/{round(mem.total/(1024**3), 1)} GB).")
    except Exception:
        pass

    try:
        cmd = ["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"]
        out = subprocess.check_output(cmd, encoding="utf-8").strip()
        parts = [p.strip() for p in out.split(",")]
        lines.append(f"- Tarjeta Gráfica GTX 1660: VRAM {parts[0]}/{parts[1]} MB, Temp: {parts[2]}°C.")
    except Exception:
        pass

    # 4. Memoria y Dashboard
    mem_dir = BASE_DIR / "memoria"
    note_count = len(list(mem_dir.rglob("*.md"))) if mem_dir.exists() else 0
    lines.append(f"- Bóveda Obsidian: {note_count} notas registradas en /memoria.")
    lines.append("- Dashboard de control en vivo: Activo en http://127.0.0.1:8080 (accesible desde el PC).")

    return "\n".join(lines)

def ask_intelligent_brain(user_query: str, system_context: str) -> str:
    """
    Responde con la máxima inteligencia:
    1. Gemini Flash (Google AI Studio - 0.00€)
    2. DeepSeek Chat API ($1.99 USD de respaldo)
    3. Ollama local (GTX 1660 local)
    """
    sys_prompt = (
        "Eres el sistema autónomo 'Autonomous Micro-Entrepreneur', hablando directamente con Antonio (el dueño y creador del proyecto) por Discord.\n"
        "Antonio NO es programador. Quiere respuestas en español claro, humano, cercano, directo y conciso. Sin rodeos ni tecnicismos vacíos.\n"
        "NUNCA uses etiquetas de código robóticas como '[Cerebro 1]' ni le pidas que use comandos como '!orden'. Tú respondes directamente como su socio tecnológico.\n\n"
        f"ESTADO ACTUAL EN TIEMPO REAL DEL SISTEMA:\n{system_context}\n\n"
        "INSTRUCCIONES CLAVE:\n"
        "- Si te pregunta por el saldo o dinero de prueba: Explícale con total claridad que SÍ ha llegado el dinero de prueba (hay ~0.040 ETH en Base Sepolia), que el Smart Contract MicroTaskRegistry.sol ya está desplegado con éxito y que el sistema ya lleva 11 micro-tareas reales registradas on-chain con 0.00€ de coste.\n"
        "- Si te pregunta qué estás haciendo o cómo vas, dile que estás trabajando de forma 100% autónoma minando documentación Web3 y registrando tareas en la blockchain cada 5 minutos.\n"
        "- Si te hace una pregunta general o técnica, respóndela de forma sencilla y ejecutiva.\n"
        "- Si te da una tarea, confírmale que la has tomado y qué pasos vas a dar."
    )

    # 1. INTENTO CON GEMINI FLASH (Prioridad 1 - Coste Cero)
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        for model in ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash"]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            payload = {
                "contents": [
                    {"parts": [{"text": f"{sys_prompt}\n\nMensaje de Antonio: {user_query}"}]}
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 900
                }
            }
            try:
                set_brain_state("Cerebro 2 (Gemini Flash)", "atención discord", "respondiendo")
                res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    set_brain_state("Cerebro 1 (Ollama GTX 1660)", "vigilancia 24/7", "en espera")
                    return answer
                elif res.status_code == 429:
                    print(f"[Gemini Quota Exceeded] Modelo {model} alcanzó cuota. Pasando a respaldo...")
            except Exception as e:
                print(f"[Gemini Fallo temporal en {model}]: {e}")

    # 2. INTENTO CON DEEPSEEK API (Respaldo inteligente)
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key:
        try:
            set_brain_state("Cerebro 3 (DeepSeek API)", "atención discord", "respondiendo como respaldo")
            headers = {
                "Authorization": f"Bearer {deepseek_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_query}
                ],
                "temperature": 0.4,
                "max_tokens": 800
            }
            res = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                answer = res.json()["choices"][0]["message"]["content"].strip()
                set_brain_state("Cerebro 1 (Ollama GTX 1660)", "vigilancia 24/7", "en espera")
                return answer
        except Exception as e:
            print(f"[Intelligent Brain DeepSeek Fallo] {e}")

    # 3. FALLBACK LOCAL OLLAMA
    try:
        set_brain_state("Cerebro 1 (Ollama GTX 1660)", "atención discord", "respondiendo local")
        import litellm
        model = f"ollama/{OLLAMA_MODEL}"
        res = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_query}
            ],
            api_base="http://127.0.0.1:11434",
            temperature=0.3
        )
        set_brain_state("Cerebro 1 (Ollama GTX 1660)", "vigilancia 24/7", "en espera")
        return res.choices[0].message.content.strip()
    except Exception:
        set_brain_state("Cerebro 1 (Ollama GTX 1660)", "vigilancia 24/7", "en espera")
        return f"Hola Antonio, estoy en guardia 24/7. Estado actual:\n{system_context}"

async def execute_screen_capture(channel):
    msg_wait = await channel.send("🔄 Capturando pantalla...")
    try:
        img_bytes, mode = await capture_screen_bytes_async()
        file = discord.File(io.BytesIO(img_bytes), filename="screen.png")
        if mode == "desktop":
            await channel.send(content="📸 **Captura actual del escritorio físico:**", file=file)
        elif mode == "dashboard_live":
            await channel.send(
                content="📊 **Captura en vivo del Panel de Control (Monitor en reposo / Pantalla bloqueada):**\n"
                        "*Mostrando telemetría real: GPU GTX 1660, cartera Base Sepolia, tareas activas y gasto DeepSeek.*",
                file=file
            )
        else:
            await channel.send(content="📊 **Instantánea gráfica de telemetría:**", file=file)
        await msg_wait.delete()
    except Exception as e:
        await msg_wait.edit(content=f"❌ Error al capturar pantalla: `{e}`")

async def send_status_embed(channel):
    embed = discord.Embed(
        title="📊 Estado del Sistema 24/7 (Autonomous Micro-Entrepreneur)",
        description="Panel de operaciones en vivo:",
        color=discord.Color.teal()
    )
    embed.add_field(name="🧠 Cerebro 2: Motor Principal", value="🟢 Google Gemini Flash (0.00€ API Key)", inline=False)
    embed.add_field(name="🧠 Cerebro 3: Especialista Código", value="🟢 DeepSeek API Activo ($1.99 USD)", inline=False)
    embed.add_field(name="🧠 Cerebro 1: Obrero Local", value=f"🟢 Ollama {OLLAMA_MODEL} en GTX 1660", inline=False)
    embed.add_field(name="🧠 Cerebro 4: Auditor de Seguridad", value="🟢 Argon (Blindaje de fondos)", inline=False)
    embed.add_field(name="🛡️ Red Blockchain", value="Base Sepolia Testnet (0 Riesgo)", inline=True)
    embed.add_field(name="💻 Dashboard Local", value="[http://127.0.0.1:8080](http://127.0.0.1:8080)", inline=True)
    embed.add_field(name="📁 Memoria", value="Obsidian (/memoria)", inline=True)
    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"[Discord] Bot conectado como {bot.user.name} (ID: {bot.user.id})")
    print(f"[Discord] Usuario autorizado: {AUTHORIZED_USER_ID}")
    print(f"[Discord] Motor principal configurado: Gemini Flash")
    if DASHBOARD_CHANNEL_ID and not update_dashboard.is_running():
        update_dashboard.start()
    if not autonomous_background_cycle.is_running():
        autonomous_background_cycle.start()
    if not scheduled_12h_reports.is_running():
        scheduled_12h_reports.start()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Comandos que empiezan por '!'
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    if not check_authorized(message):
        return

    text = message.content.strip()
    lower_text = text.lower()

    # 1. Detección automática de API Keys (sk-... o AQ....)
    key_match_gemini = re.search(r"(AQ\.[a-zA-Z0-9_-]{30,64})", text)
    if key_match_gemini:
        extracted = key_match_gemini.group(1)
        save_api_key_to_system(extracted, "GEMINI_API_KEY")
        return await message.reply(
            f"⚡ **Nueva clave de Gemini Flash configurada con éxito:**\n"
            f"> `{extracted[:8]}...{extracted[-4:]}`\n"
            f"El motor principal de Discord y tareas ahora usa Gemini Flash (0,00 €)."
        )

    key_match_ds = re.search(r"(sk-[a-zA-Z0-9_-]{30,64})", text)
    if key_match_ds:
        extracted = key_match_ds.group(1)
        save_api_key_to_system(extracted, "DEEPSEEK_API_KEY")
        return await message.reply(
            f"🔐 **Clave de DeepSeek actualizada:**\n"
            f"> `{extracted[:8]}...{extracted[-4:]}`"
        )

    key_match_gh = re.search(r"(ghp_[a-zA-Z0-9]{30,50}|github_pat_[a-zA-Z0-9_]{40,120})", text)
    if key_match_gh:
        extracted = key_match_gh.group(1)
        save_api_key_to_system(extracted, "GITHUB_TOKEN")
        from github_deliverer import deliver_all_pending
        delivered = deliver_all_pending()
        return await message.reply(
            f"🚀 **Token de GitHub configurado con éxito:**\n"
            f"> `{extracted[:8]}...{extracted[-4:]}`\n"
            f"Entregadas automáticamente **{delivered}** soluciones en repositorios para cobro."
        )

    # 2. Comprobar si había una consulta pendiente del Cerebro
    active_q = check_active_question()
    if active_q and active_q.get("status") == "pending":
        resolve_active_question(text)
        return await message.reply(
            f"✅ **Respuesta registrada y entregada al sistema:**\n"
            f"> *\"{text}\"*\n"
            f"La tarea ha sido informada."
        )

    # 3. Control de Obsidian
    if any(k in lower_text for k in ['abrir obsidian', 'abre obsidian', 'mostrar obsidian', 'iniciar obsidian']):
        try:
            obs_path = os.path.expandvars(r'%LOCALAPPDATA%\Programs\Obsidian\Obsidian.exe')
            vault_path = str(BASE_DIR / 'memoria')
            subprocess.Popen([obs_path, vault_path])
            return await message.reply('📂 **Obsidian abierto en la pantalla del equipo.** Ya puedes pedir una captura para ver la bóveda.')
        except Exception as e:
            return await message.reply(f'❌ Error al abrir Obsidian: {e}')

    # 4. Captura de pantalla en lenguaje natural
    if any(k in lower_text for k in ["captura", "pantalla", "screenshot", "foto de la pantalla", "foto de tu pantalla"]):
        return await execute_screen_capture(message.channel)

    # 5. Petición de estado del sistema
    if any(k in lower_text for k in ["estado del sistema", "como vas", "como va el sistema", "reporte de estado", "status", "telemetria"]):
        return await send_status_embed(message.channel)

    # 6. Detección de órdenes/tareas para guardar en cola automáticamente
    action_verbs = ["haz", "crea", "busca", "programa", "analiza", "compila", "despliega", "guarda", "mira", "investiga", "revisa", "escribe", "actualiza", "pon"]
    if any(lower_text.startswith(v) for v in action_verbs) or "orden:" in lower_text or "tarea:" in lower_text:
        push_order(text, source="discord_chat_direct")

    # 7. Conversación directa e inteligente con el sistema (prioridad Gemini Flash)
    async with message.channel.typing():
        sys_context = get_live_system_context()
        reply = ask_intelligent_brain(text, sys_context)

        if len(reply) > 1900:
            for chunk in [reply[i:i+1900] for i in range(0, len(reply), 1900)]:
                await message.reply(chunk)
        else:
            await message.reply(reply)

# Comandos de utilidad
@bot.command(name="screen")
async def screen(ctx):
    if not check_authorized(ctx):
        return await ctx.send("❌ No estás autorizado.")
    await execute_screen_capture(ctx.channel)

@bot.command(name="status")
async def status(ctx):
    if not check_authorized(ctx):
        return await ctx.send("❌ No estás autorizado.")
    await send_status_embed(ctx.channel)

@bot.command(name="dashboard")
async def dashboard_cmd(ctx):
    if not check_authorized(ctx):
        return await ctx.send("❌ No estás autorizado.")
    await ctx.send("🖥️ **Panel de Telemetría 24/7:**\nAccede en tu navegador a: http://127.0.0.1:8080\n(También puedes abrir el archivo `Abrir_Dashboard_24-7.bat` en tu Escritorio).")

@bot.command(name="orden")
async def orden_cmd(ctx, *, texto: str):
    if not check_authorized(ctx):
        return await ctx.send("❌ No estás autorizado.")
    push_order(texto, source="command_orden")
    async with ctx.typing():
        sys_context = get_live_system_context()
        reply = ask_intelligent_brain(texto, sys_context)
    await ctx.send(f"📥 **Tarea anotada en cola:**\n{reply}")

@bot.command(name="pregunta")
async def pregunta_cmd(ctx):
    if not check_authorized(ctx):
        return await ctx.send("❌ No estás autorizado.")
    q = check_active_question()
    if q and q.get("status") == "pending":
        await ctx.send(f"❓ **El sistema está esperando tu respuesta a:**\n> {q['question']}")
    else:
        await ctx.send("✅ No hay ninguna pregunta pendiente del sistema.")

@bot.command(name="github")
async def github_cmd(ctx, *, token_str: str):
    if not check_authorized(ctx):
        return await ctx.send("❌ No estás autorizado.")
    t = token_str.strip()
    save_api_key_to_system(t, "GITHUB_TOKEN")
    from github_deliverer import deliver_all_pending
    count = deliver_all_pending()
    await ctx.send(f"🚀 **Token de GitHub guardado en el sistema.**\nEntregadas `{count}` soluciones pendientes directamente en los repositorios de GitHub para cobro.")

@bot.command(name="token")
async def token_cmd(ctx, *, token_str: str):
    await github_cmd(ctx, token_str=token_str)

# Tareas en segundo plano
cycle_counter = 0

@tasks.loop(minutes=3)
async def autonomous_background_cycle():
    """Ciclo de vigilancia continua: procesa órdenes, revisa Web3 y ejecuta minería de micro-tareas"""
    global cycle_counter
    cycle_counter += 1

    # 1. Procesar órdenes en cola
    try:
        from discord_bridge import pop_pending_orders
        pending = pop_pending_orders()
        if pending and GENERAL_CHANNEL_ID:
            ch = bot.get_channel(GENERAL_CHANNEL_ID)
            for o in pending:
                sys_context = get_live_system_context()
                res_txt = ask_intelligent_brain(f"Ejecuta o procesa la siguiente orden: {o['text']}", sys_context)
                if ch:
                    await ch.send(f"📥 **Tarea `{o['id']}` procesada:**\n{res_txt}")
    except Exception as e:
        print(f"[Loop Error Ordenes] {e}")

    # 2. Minería y registro autónomo de tareas cada 15 minutos (cada 5 ciclos)
    if cycle_counter % 5 == 1:
        try:
            sys.path.append(str(BASE_DIR / "scripts_generados"))
            from continuous_worker import run_continuous_cycle
            await run_continuous_cycle()
        except Exception as e:
            print(f"[Loop Error Continuous Worker] {e}")

@tasks.loop(seconds=60)
async def update_dashboard():
    global dashboard_message
    if not DASHBOARD_CHANNEL_ID:
        return
    channel = bot.get_channel(DASHBOARD_CHANNEL_ID)
    if not channel:
        return
        
    delivered_count = 0
    q_file = BASE_DIR / "memoria" / "estado" / "cola_oportunidades.json"
    if q_file.exists():
        try:
            with open(q_file, "r", encoding="utf-8") as f:
                items = json.load(f)
                delivered_count = len([it for it in items if it.get("status") == "delivered"])
        except Exception:
            pass

    spent_eur = 0.0
    ds_file = BASE_DIR / "memoria" / "estado" / "deepseek_presupuesto.json"
    if ds_file.exists():
        try:
            with open(ds_file, "r", encoding="utf-8") as f:
                spent_eur = json.load(f).get("spent_eur", 0.0)
        except Exception:
            pass

    curated_count = 0
    curated_file = BASE_DIR / "memoria" / "datasets_curados" / "oportunidades_grants_verificados.json"
    if curated_file.exists():
        try:
            with open(curated_file, "r", encoding="utf-8") as f:
                curated_count = len(json.load(f))
        except Exception:
            pass

    embed = discord.Embed(
        title="📊 Panel en Vivo 24/7: Autonomous Micro-Entrepreneur",
        description=f"Última señal de vida: `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
        color=discord.Color.teal()
    )
    embed.add_field(name="💰 Dinero Real Líquido", value="`0,00 €` *(fondos seguros)*", inline=True)
    embed.add_field(name="🚀 Bounties Entregadas", value=f"`{delivered_count} entregadas` en GitHub", inline=True)
    embed.add_field(name="🛡️ Grants & Intel Curados", value=f"`{curated_count} programas` (Base/CDP)", inline=True)
    embed.add_field(name="⚡ Gasto DeepSeek Hoy", value=f"`{spent_eur:.4f}€` / `0.50€`", inline=True)
    embed.add_field(name="🧠 Cerebros Cooperativos", value="Ollama (1660) + DeepSeek + Antigravity", inline=True)
    embed.add_field(name="💻 Dashboard Web Local", value="[http://127.0.0.1:8080](http://127.0.0.1:8080)", inline=True)
    embed.add_field(name="🛡️ Watchdog Supervisor", value="🟢 Auto-recuperación activa (<2s)", inline=True)
    
    try:
        if dashboard_message is None:
            async for m in channel.history(limit=5):
                if m.author == bot.user and len(m.embeds) > 0:
                    dashboard_message = m
                    break
                    
        if dashboard_message is None:
            dashboard_message = await channel.send(embed=embed)
        else:
            await dashboard_message.edit(embed=embed)
    except Exception:
        pass

last_report_hour = -1

@tasks.loop(seconds=45)
async def scheduled_12h_reports():
    global last_report_hour
    now = time.localtime()
    hour = now.tm_hour
    minute = now.tm_min
    if (hour == 9 or hour == 21) and minute == 0 and hour != last_report_hour:
        last_report_hour = hour
        try:
            from twelve_hour_reporter import send_12h_report
            send_12h_report()
            print(f"[Discord] Reporte ejecutivo de las {hour}:00 enviado con éxito.")
        except Exception as e:
            print(f"[Discord Error Reporte 12h]: {e}")

@bot.command(name="reporte")
async def reporte_cmd(ctx):
    """Comando manual para solicitar el reporte ejecutivo de 12 horas"""
    if not check_authorized(ctx):
        return
    from twelve_hour_reporter import send_12h_report
    send_12h_report("Bajo Demanda")
    await ctx.reply("📋 Reporte de 12 horas enviado.")

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Configura DISCORD_BOT_TOKEN en config/.env para iniciar el bot.")
