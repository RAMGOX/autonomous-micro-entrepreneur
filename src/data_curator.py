"""
Data Curator: Generador autónomo de datasets de inteligencia Web3 y Grants.
Extrae datos limpios con Crawl4AI y estructura oportunidades verificadas con coste marginal 0,00€.
"""
import os
import sys
import json
import time
import asyncio
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from brain_router import route_task
from discord_bridge import notify_user_discord

OUTPUT_DIR = BASE_DIR / "memoria" / "datasets_curados"
OUTPUT_JSON = OUTPUT_DIR / "oportunidades_grants_verificados.json"
OUTPUT_MD = OUTPUT_DIR / "oportunidades_grants_verificados.md"

SOURCES = [
    {
        "name": "Base Ecosystem & Grants",
        "url": "https://base.org/ecosystem",
        "category": "Ecosistema L2 Base"
    },
    {
        "name": "Coinbase Developer Platform Docs",
        "url": "https://docs.cdp.coinbase.com",
        "category": "Developer Grants"
    }
]

def safe_print(text: str):
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    except Exception:
        pass

async def scrape_source(url: str) -> str:
    """Extrae markdown limpio usando crawl4ai en modo headless"""
    try:
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            if result.success and result.markdown:
                return result.markdown[:3000]
    except Exception as e:
        safe_print(f"[Curator Warning] Fallback requests para {url}: {e}")
    
    # Fallback requests estándar si crawl4ai requiere dependencias de navegador adicionales
    import requests
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "AutonomousCurator/1.0"})
        if r.status_code == 200:
            import re
            text = re.sub(r"<[^>]+>", " ", r.text)
            text = re.sub(r"\s+", " ", text)
            return text[:3000]
    except Exception:
        pass
    return ""

def process_and_save_intel():
    """Ejecuta el ciclo de extracción y generación de dataset"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Data Curator] Iniciando minería de inteligencia...")

    dataset = []
    if OUTPUT_JSON.exists():
        try:
            with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                dataset = json.load(f)
        except Exception:
            dataset = []

    for src in SOURCES:
        name = src["name"]
        url = src["url"]
        category = src["category"]
        safe_print(f"[Data Curator] Extrayendo fuente: {name} ({url})")

        raw_text = asyncio.run(scrape_source(url))
        if not raw_text:
            continue

        prompt = f"""Analiza este extracto de la web '{name}' ({url}):
{raw_text[:2000]}

Extrae un listado estructurado de iniciativas activas, subvenciones (grants), faucets o herramientas para desarrolladores.
Responde estrictamente en formato JSON con la siguiente estructura:
[
  {{
    "iniciativa": "Nombre",
    "tipo": "Grant / Faucet / Herramienta",
    "red": "Base / Ethereum",
    "valor_estimado": "Monto o gratuito",
    "enlace": "{url}",
    "descripcion_resumida": "Detalle breve"
  }}
]
"""
        ans = route_task(
            task_type="general",
            prompt=prompt,
            difficulty=2,
            system_prompt="Eres un curador de datos financieros y Web3. Genera JSON estricto sin texto introductorio."
        )
        content = ans.get("response", "[]")

        import re
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                items = json.loads(match.group(0))
                for it in items:
                    it["fuente"] = name
                    it["actualizado_el"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    dataset.append(it)
                safe_print(f"[Data Curator] {len(items)} registros extraídos de {name}.")
            except Exception as e:
                safe_print(f"[Data Curator Error parseando JSON]: {e}")

    # Guardar JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    # Generar Markdown exportable
    md_lines = [
        f"# 📊 Directorio de Inteligencia Web3 y Developer Grants",
        f"- **Última actualización:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Registros totales:** {len(dataset)}",
        f"- **Generado por:** Autonomous Data Curator (Costo 0,00€)\n",
        f"| Iniciativa | Tipo | Red | Valor | Enlace |",
        f"|---|---|---|---|---|"
    ]
    for d in dataset[-30:]:
        md_lines.append(f"| {d.get('iniciativa', '-')} | {d.get('tipo', '-')} | {d.get('red', '-')} | {d.get('valor_estimado', '-')} | [{d.get('fuente', 'Link')}]({d.get('enlace', '#')}) |")

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    safe_print(f"[Data Curator] Dataset consolidado en: {OUTPUT_MD}")
    return len(dataset)

if __name__ == "__main__":
    process_and_save_intel()
