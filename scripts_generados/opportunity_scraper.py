"""
Opportunity Scraper: Extractor autnomo de datos Web3 usando Crawl4AI y 4-Cerebros
Inspirado en el pipeline de datos de ElizaOS y LLMLingua
"""
import os
import sys
import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from brain_router import route_task

ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

async def scrape_and_analyze(url: str, opportunity_theme: str):
    print("=" * 60)
    print(f" CRAWL4AI SCRAPER - MINERA DE DATOS: {opportunity_theme}")
    print(f" Target URL: {url}")
    print("=" * 60)
    
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
    
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        exclude_external_links=True
    )
    
    markdown_content = ""
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=config)
        if result.success:
            markdown_content = result.markdown
            print(f"-> Extraccin exitosa: {len(markdown_content)} caracteres de Markdown limpio.")
        else:
            print(f"[Aviso] Fallo de crawl en {url}: {result.error_message}")
            return None

    # Recortar o resumir contenido para no saturar memoria
    clean_sample = markdown_content[:2500]
    
    prompt = f"""Analiza la siguiente informacin extrada de la web '{url}' sobre '{opportunity_theme}'.
Identifica:
1. Oportunidades de micro-servicios digitales o integraciones para un agente autnomo en Base Sepolia.
2. Contratos inteligentes, herramientas gratuitas o APIs disponibles.
3. Recomendacin prctica de implementacin con coste marginal cero.

Informacin:
{clean_sample}
"""

    print("-> Enviando contenido al Enrutador Inteligente (Cerebro 1/3)...")
    analysis = route_task(
        task_type="code",
        prompt=prompt,
        difficulty=5,
        system_prompt="Eres el Analista Estratgico del proyecto 'Autonomous Micro-Entrepreneur'. Extrae oportunidades reales, concretas y tcnicas."
    )
    
    output_text = analysis.get("response", "Sin anlisis.")
    brain_used = analysis.get("brain", "Cerebro")
    print(f"-> Anlisis completado por: {brain_used}")
    
    # Guardar en Obsidian
    memoria_file = BASE_DIR / "memoria" / "estrategias" / "oportunidades_detectadas.md"
    entry = f"""
## [{time.strftime("%Y-%m-%d %H:%M:%S")}] Oportunidad: {opportunity_theme}
- **Fuente:** `{url}`
- **Analizado por:** {brain_used}
- **Dictamen:**
{output_text}

---
"""
    with open(memoria_file, "a", encoding="utf-8") as f:
        f.write(entry)
        
    print(f"-> Oportunidad registrada en: memoria/estrategias/oportunidades_detectadas.md")
    print("=" * 60)
    return output_text

if __name__ == "__main__":
    target = "https://docs.base.org/docs/chain/network-information"
    theme = "Base Sepolia Network & Testnet Infrastructure"
    asyncio.run(scrape_and_analyze(target, theme))
