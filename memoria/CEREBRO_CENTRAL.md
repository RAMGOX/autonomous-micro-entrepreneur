# 🧠 CEREBRO CENTRAL — Autonomous Micro-Entrepreneur v3.0

> **Estado de Arquitectura:** Producción v3.0 (Mobile-First, 100% Datos Reales, Cero Sepolia, Cero Gasto Oculto GPU)

---

## 📱 1. Centro de Mando Móvil (Discord + Web Exterior)
- **Bandeja de Aprobación Móvil:** [[ENTREGAS_PARA_REVISAR]] (`memoria/estado/bandeja_revision.json`)
  - Todos los trabajos resueltos llegan a `#general` en Discord con 4 botones táctiles: **✅ Aprobar**, **📄 Ver Archivo**, **✏️ Pedir Cambios** (abre formulario en el móvil y regenera el trabajo) y **🗑️ Descartar**.
- **Atajos rápidos en Discord (sin `!`):**
  - `revisar` — Muestra las entregas pendientes con sus botones.
  - `panel` — Devuelve tu enlace móvil autenticado para entrar desde fuera de casa.
  - `estado` — Saldos reales en Base Mainnet, presupuesto DeepSeek (`0.50 €/día`) y hardware.
  - `bounties` — Lista las mejores oportunidades en `$USD` filtradas en cola.
  - `apify` — Estado de los Actores Apify Store / MCP.
  - `prompts` — Envía los prompts listos para tus chats paralelos de Gemini Pro.
  - `captura` — Captura física completa de todas las ventanas del escritorio.

---

## 🚀 2. Los 3 Motores de Ingresos Reales
1. **Motor 1 — Bounties de Software Verificadas (`$25 – $3,000 USD`):**
   - Panel Obsidian: [[MOTOR_1_BOUNTIES_GITHUB]]
   - Código: `src/github_bounty_hunter.py` + `src/poidh_scanner.py` + `src/deepseek_solver.py`
   - Regla de oro: Cero comentarios automáticos en GitHub y cero reclamos ciegos en POIDH sin tu aprobación móvil.
2. **Motor 2 — Actores Apify Store & Servidores MCP (Ingresos Recurrentes / Pay-Per-Event):**
   - Panel Obsidian: [[MOTOR_2_APIFY_ACTORS]]
   - Código: `src/apify_actor_factory.py` (`apify_actors/eu-public-tenders-b2b` y `apify_actors/base-dex-rug-auditor`)
3. **Motor 3 — Pasarela x402 en Base Mainnet (`USDC` + `ETH`):**
   - Código: `src/x402_gateway.py` + `src/dashboard_server.py` + `src/tunnel_manager.py`
   - Endpoints comerciales:
     - `/api/v1/x402/scrape?url=...` (`$0.02 USDC` — extracción residencial limpia con protección anti-SSRF)
     - `/api/v1/x402/intel?topic=all` (`$0.05 USDC` — inteligencia DeFi Base + Bounties curadas)
     - `POST /api/v1/x402/solve` (`$0.25 USDC` — inferencia técnica bajo demanda)

---

## ⚡ 3. Jerarquía de Cerebros y Control de Costes
- **Chats Paralelos Gemini Pro (`0,00 €` API):** [[PROMPTS_CHATS_PARALELOS]] — Fuerza pesada de ingeniería y auditoría en bucles cada 4h / 8h.
- **Gemini Flash API (`GEMINI_API_KEY`):** Prioridad gratuita (`0,00 €`). Cuando caduque la clave gratuita, `src/brain_router.py` detecta `401/403/429` y la desactiva automáticamente sin interrumpir el sistema.
- **DeepSeek API (`DEEPSEEK_API_KEY`):** Tope estricto atómico de **`0.50 €/día`** en `memoria/estado/deepseek_presupuesto.json` + consulta de saldo real en vivo (`https://api.deepseek.com/user/balance`).
- **Ollama Local (`GTX 1660`):** Respaldo gratuito de emergencia (`0,00 €`). Permanece en `0W` / `0%` en reposo para no consumir electricidad ni saturar la gráfica.

---

## 🗂️ 4. Mapa Limpio de Archivos de Estado
- `memoria/estado/cola_oportunidades.json` — Cola atómica normalizada de bounties abiertas.
- `memoria/estado/bandeja_revision.json` — Entregas listas esperando tu aprobación móvil.
- `memoria/estado/deepseek_presupuesto.json` — Control diario de gasto IA (`<= 0.50 €`).
- `memoria/estado/recompensas_cobradas.json` — Contabilidad real auditada en USD/EUR.
- `memoria/estado/x402_ventas.json` — Cobros on-chain verificados en Base Mainnet.
- `memoria/historico/scripts_archivo/` — Archivo histórico de 141 scripts antiguos retirados de `src/` y `tools/`.
