# 🚀 Autonomous Micro-Entrepreneur (24/7)

Sistema autónomo de generación de micro-ingresos digitales y curación de datos operando de manera independiente en Windows 10 con GPU dedicada NVIDIA GeForce GTX 1660 (6 GB VRAM).

---

## 🏛️ Arquitectura de los 4 Cerebros

1. **Cerebro 1: El Obrero Local (0,00 €)**
   * **Motor:** Ollama ejecutando `qwen2.5-coder:7b-instruct-q4_K_S` acelerado por CUDA en la GTX 1660.
   * **Función:** Monitoreo 24/7, escucha de Discord, extracción con Crawl4AI, organización de memoria en Obsidian.
2. **Cerebro 2: El Director de Operaciones (0,00 € adicionales)**
   * **Motor:** Gemini 3.8 Flash (en ventana de Antigravity Pro).
   * **Función:** Planificación macro, síntesis de datos, redacción y conversación.
3. **Cerebro 3: El Especialista de Código / CTO (~0,35 €/día máx)**
   * **Motor:** DeepSeek API con limitador estricto de gasto de tokens (`litellm`).
   * **Función:** Programación compleja, llamadas a smart contracts, depuración. Si se agota el cupo diario de 0.35€, deriva a Gemini Flash.
4. **Cerebro 4: El Arquitecto Supremo**
   * **Motor:** Argon (cupo semanal reservado).
   * **Función:** Decisiones críticas de alto impacto (dificultad ≥ 8/10) y auditorías.

---

## 🛡️ Stack de Optimización de Tokens

* **`tokless` (v1.0.3):** Integrado directamente con Antigravity. Emplea `RTK`, `CodeGraph`, `Context-Mode` y reglas deterministas de Karpathy para comprimir logs y reducir context bloat sin gastar tokens.
* **`LLMLingua`:** Compresión semántica de prompts y textos entre un 50% y 75% antes de enviarlos a modelos de pago.
* **`LiteLLM`:** Enrutador con circuit breaker y control estricto de presupuesto diario de 0,35 € y semanal de 2,50 €.
* **`Outlines`:** Máscaras de logits para respuestas estructuradas en JSON/Pydantic sin alucinaciones ni reintentos.
* **`Crawl4AI`:** Extracción web ultralimpia en Markdown nativo eliminando código HTML y publicidad.

---

## 📁 Estructura del Proyecto

```
autonomous-micro-entrepreneur/
├── config/
│   ├── .env                 # Claves API y configuración privada
│   └── .env.example         # Plantilla de configuración
├── memoria/                 # Memoria persistente a largo plazo (Obsidian)
│   ├── lecciones/           # Registro de errores y soluciones aprendidas
│   ├── estrategias/         # Ideas de micro-servicios y airdrops
│   └── estado/              # Registro diario de balance y métricas
├── scripts_generados/       # Scripts autónomos generados de forma aislada
├── src/
│   ├── brain_router.py      # Enrutador inteligente de los 4 cerebros y presupuestos
│   ├── discord_bot.py       # Bot privado con comando !screen y dashboard
│   └── obsidian_memory.py   # Gestor de memoria persistente
├── tools/
│   └── tokless/             # Repositorio y herramientas de tokless
├── SYSTEM_PROMPT.md         # Constitución y reglas maestras operativas
└── README.md
```
