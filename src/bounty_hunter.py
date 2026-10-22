"""
Bounty Hunter: Rastreador autónomo de micro-recompensas y bounties en Base / Web3 / Python.
Monitorea issues y tareas con recompensa real en USDC/tokens en Base.
Evalúa la viabilidad con Cerebro 2 (Gemini Flash) y redacta la solución.
"""
import os
import sys
import time
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from brain_router import route_task
from discord_bridge import notify_user_discord
from opportunity_queue import push_opportunity, prune_expired_opportunities

BOUNTIES_MEMORIA = BASE_DIR / "memoria" / "estrategias" / "bounties_detectadas.md"
SEEN_BOUNTIES_FILE = BASE_DIR / "memoria" / "estado" / "bounties_vistas.json"

def safe_print(text: str):
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    except Exception:
        pass

def load_seen_bounties() -> set:

    if SEEN_BOUNTIES_FILE.exists():
        try:
            with open(SEEN_BOUNTIES_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_seen_bounties(seen: set):
    SEEN_BOUNTIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_BOUNTIES_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, indent=2)

def scan_github_bounties():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    token = os.getenv("GITHUB_TOKEN")

    queries = [
        "is:issue is:open \"algora.io\" in:body",
        "is:issue is:open \"polar.sh\" in:body",
        "is:issue is:open \"opire.dev\" in:body",
        "is:issue is:open \"poidh\" in:title,body",
        "is:issue is:open label:bounty USDC in:title,body",
        "is:issue is:open label:bounty USDT in:title,body",
        "is:issue is:open label:bounty ETH in:title,body",
        "is:issue is:open \"bounty reward\" USDC in:body",
        "is:issue is:open label:bounty Base in:title,body",
        "is:issue is:open \"bounty: $\" in:title",
        "is:issue is:open \"[BOUNTY] $\" in:title",
        "is:issue is:open \"bounty\" \"Solidity\" in:title,body",
        "is:issue is:open \"gitcoin\" in:title,body"
    ]

    headers = {"User-Agent": "AutonomousMicroEntrepreneur/1.0"}
    if token and token.strip() not in ("", "TU_GITHUB_TOKEN_AQUI"):
        headers["Authorization"] = f"Bearer {token.strip()}"
        headers["Accept"] = "application/vnd.github+json"

    seen = load_seen_bounties()
    found_any = False
    new_count = 0

    safe_print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Bounty Hunter] Escaneando GitHub ({'Autenticado con Token' if 'Authorization' in headers else 'Anonimo'})...")

    for q in queries:
        url = f"https://api.github.com/search/issues?q={requests.utils.quote(q)}&sort=created&order=desc&per_page=15"
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code == 403:
                safe_print(f"[Bounty Hunter Warning] GitHub Rate limit temporal en busqueda: {r.headers.get('x-ratelimit-remaining')}/{r.headers.get('x-ratelimit-limit')}")
                break
            if r.status_code != 200:
                continue
            items = r.json().get("items", [])
            for item in items:
                issue_id = str(item.get("id"))
                if issue_id in seen:
                    continue
                seen.add(issue_id)
                found_any = True
                new_count += 1
                
                title = item.get("title", "")
                html_url = item.get("html_url", "")
                if any(bad in html_url for bad in ["Iamgoofball", "claude-honeypot", "algora-io/algora", "whocards/whocards-platform"]):
                    continue
                body = (item.get("body") or "")[:1500]

                text_combined = (title + " " + body).lower()
                spam_words = ["donate", "donation", "looking for sponsors", "want to fund", "interested in funding", "support my dev", "support dev", "donate $", "airdrop claim"]
                if any(w in text_combined for w in spam_words):
                    safe_print(f"[Bounty Filter] Descartada peticion de donacion/spam: {title[:45]}")
                    continue

                is_escrow = any(k in text_combined for k in ["algora.io", "polar.sh", "poidh", "gitcoin", "escrow", "smart contract", "0x"])
                safe_print(f"\n[Bounty Detectada] {'[ESCROW ON-CHAIN]' if is_escrow else ''} {title} ({html_url})")
                
                # Evaluar viabilidad y valor monetario real con los Cerebros
                prompt = f"""Analiza esta recompensa/bounty de GitHub:
Título: {title}
Enlace: {html_url}
Descripción:
{body}

Responde de forma estricta:
1. VALOR MONETARIO REAL: ¿Qué moneda/token pagan? ¿Tiene valor de mercado real en exchanges (USDC, USDT, ETH, SOL, USD, criptos líquidas) o es un token de prueba/puntos sin valor financiero?
2. REQUERIMIENTO TÉCNICO: ¿Qué piden programar o entregar?
3. VIABILIDAD (1-10): ¿Es una tarea viable para resolver con código ahora mismo?
"""
                ans = route_task(
                    task_type="general",
                    prompt=prompt,
                    difficulty=3,
                    system_prompt="Eres el Auditor de Recompensas del sistema. Discrimina con total rigor si el pago tiene valor financiero real convertible a dinero o si es ficticio."
                )
                analysis_text = ans.get("response", "Sin análisis.")
                
                # Guardar en Obsidian
                entry = f"""
### [{time.strftime('%Y-%m-%d %H:%M:%S')}] {title}
- **Enlace:** [{html_url}]({html_url})
- **Dictamen de Valor y Viabilidad:**
{analysis_text}

---
"""
                with open(BOUNTIES_MEMORIA, "a", encoding="utf-8") as f:
                    f.write(entry)
                    
                # Notificar a Discord con etiqueta de valor
                has_real_value = any(k in analysis_text.upper() for k in ["USDC", "USDT", "ETH", "SOL", "USD", "VALOR REAL", "LÍQUIDO", "LIQUIDO"]) and not any(k in analysis_text.upper() for k in ["SIN VALOR", "FICTICIO", "TOKEN DE PRUEBA", "PUNTOS SIN VALOR"])
                badge = "💰 RECOMPENSA CON VALOR REAL" if has_real_value else "⚠️ TOKEN/PUNTOS DE PROYECTO"
                
                # Clasificar dificultad
                diff_level = "media"
                if any(k in analysis_text.upper() for k in ["DIFICULTAD: 7", "DIFICULTAD: 8", "DIFICULTAD: 9", "DIFICULTAD: 10", "DIFICULTAD ALTA", "COMPLEJIDAD ALTA"]):
                    diff_level = "alta"
                elif any(k in analysis_text.upper() for k in ["DIFICULTAD: 1", "DIFICULTAD: 2", "DIFICULTAD: 3", "DIFICULTAD BAJA", "SENCILLO", "FÁCIL", "FACIL"]):
                    diff_level = "baja"

                # Estimar valor USD
                est_val = 0.0
                import re
                val_match = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", title + " " + body + " " + analysis_text)
                if val_match:
                    try:
                        est_val = float(val_match.group(1))
                    except Exception:
                        est_val = 5.0
                elif has_real_value:
                    est_val = 10.0

                # Registrar en la cola con TTL de 2 horas y prioridad de escrow
                push_opportunity(
                    title=title,
                    url=html_url,
                    description=body,
                    difficulty=diff_level,
                    estimated_value_usd=est_val,
                    reward_currency="USD" if has_real_value else "TOKEN",
                    is_escrow_verified=is_escrow
                )
                safe_print(f"-> Bounty evaluada y registrada en Obsidian (Discord silenciado para no spamear).")
                time.sleep(2)
        except Exception as e:
            safe_print(f"[Bounty Hunter Error] {e}")

    save_seen_bounties(seen)
    return found_any

if __name__ == "__main__":
    scan_github_bounties()
