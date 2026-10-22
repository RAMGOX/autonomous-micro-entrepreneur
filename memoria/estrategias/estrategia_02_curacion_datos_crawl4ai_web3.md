# Estrategia 02: Curación y Minería de Datos Web3 con Crawl4AI + LLMLingua

- **Tipo:** Micro-servicio digital de coste marginal cero.
- **Riesgo:** 0.00 / 10 (Sin capital en riesgo).
- **Cerebros Implicados:**
  - Cerebro 1 (GTX 1660 / Ollama): Filtrado preliminar y resumen rápido.
  - Cerebro 3 (DeepSeek API): Extracción de contratos inteligentes, APIs y esquemas JSON.

---

## 1. Fundamento Técnico (Patrón ElizaOS + Crawl4AI)
Los agentes autónomos más rentables en Web3 no operan haciendo trading ciego; operan recopilando información estructurada antes que los humanos:
1. **Extracción Limpia:** Usando `crawl4ai` en modo headless, extraemos directorios de proyectos en Base Sepolia, hackathons de Coinbase Developer Platform y tablones de micro-tareas Web3.
2. **Compresión Masiva:** `LLMLingua` comprime el texto de la web un 60%, eliminando código basura y anuncios.
3. **Generación de Oportunidades:** El modelo local detecta si hay faucets activas, bounties abiertas o airdrops en testnet y genera una ficha Markdown en `/memoria/estrategias/`.

---

## 2. Fuentes de Datos Prioritarias
- **Base Ecosystem:** `https://base.org/ecosystem`
- **Coinbase Developer Platform Docs:** `https://docs.cdp.coinbase.com`
- **Faucets Base Sepolia:**
  - `https://faucets.chain.link/base-sepolia`
  - `https://www.alchemy.com/faucets/base-sepolia`
  - `https://learnweb3.io/faucets/base_sepolia`

---

## 3. Salida de Datos Esperada
Cada ciclo de scraping genera un reporte con:
- Nombre del protocolo / oportunidad.
- Red y contrato en Base Sepolia.
- Requisitos de ejecución y coste de gas estimado (en testnet = 0€).
- Acción recomendada para el agente autónomo.
