# DOCUMENTO DE TRASPASO Y ESTADO DEL SISTEMA (HANDOVER 24/7)
Fecha de última actualización: 2026-10-22 18:47 CET
Operador / Cartera: `0x02c1F87F514493F359Afc0B3ff6b587434770361` (Base Mainnet / Cross-chain)

---

## 1. MISIÓN Y OPERATIVA ACTUAL
El sistema funciona 24/7 de forma 100% desatendida en un PC local (Ryzen 5 3600, GTX 1660 6GB VRAM, Windows 10 Pro):
- **Objetivo económico:** Capturar y resolver bounties y micro-recompensas de código y smart contracts en GitHub/Web3, cobrando en USDC / ETH / USDT / tokens directamente a la billetera del operador.
- **Entregas realizadas:** 73 soluciones entregadas directamente vía GitHub Issues/PRs por valor de **,653.00 USD** acumulados. Última entrega: [fulldecent/erc721#304](https://github.com/fulldecent/erc721/issues/304#issuecomment-6348433151) ( USD).
---

## 2. ARQUITECTURA DE CEREBROS Y DIVISIÓN DE TRABAJO

1. **Cerebro 1: Local Ollama (GTX 1660 - `qwen2.5-coder:7b-instruct-q4_K_S`):**
   - Coste: 0,00€.
   - Escanea GitHub continuamente con autenticación `GITHUB_TOKEN`.
   - Clasifica y encola en `memoria/estado/cola_oportunidades.json`.

2. **Cerebro 3: DeepSeek API (`deepseek/deepseek-chat`):**
   - Límite de gasto: **0.50€ al día** (controlado en `memoria/estado/deepseek_presupuesto.json`).
   - Se ejecuta cada 5 minutos desde `scripts_generados/autonomous_daemon.py`.
   - Atiende exclusivamente oportunidades clasificadas como **`["baja", "media"]`**.
   - Bloquea atómicamente la tarea para no pisarse con Antigravity.
   - Guarda la solución en `memoria/estrategias/soluciones_propuestas/` y notifica a Discord.

3. **Cerebro 4: Antigravity (Tú en chat principal / cron cada 8 min):**
   - Cron de ejecución: **cada 8 minutos** (`*/7 * * * *`).
   - Examina la **lista COMPLETA** (`alta`, `media`, `baja`).
   - Selecciona las 2-3 tareas más rentables en $ USD bloqueándolas atómicamente (`in_progress`).
   - Resuelve directamente o lanza 2-3 subagentes en paralelo.
   - Deriva a Argon 4 únicamente si la tarea es de dificultad extrema (≥8/10) y rentabilidad muy alta.

---

## 3. SERVICIOS Y DEMONIOS PERPETUOS

Supervisados por `src/system_watchdog.py` (auto-recuperación en <2s con `psutil`):
- `scripts_generados/autonomous_daemon.py`: Motor 24/7 (ingesta, DeepSeek cada 5m, entregas automáticas).
- `src/dashboard_server.py`: Servidor web en puerto 8080. Monitoriza balances reales de Base Mainnet (ETH y USDC) y dispara webhook a Discord ante cualquier ingreso de saldo.
- `src/discord_bot.py`: Escucha comandos de Discord y actualiza dashboard en vivo.
- `src/bounty_hunter.py`: Escáner continuo de repositorios GitHub.

---

## 4. INSTRUCCIONES PARA UN SEGUNDO CHAT DE ANTIGRAVITY

Si el usuario abre otra sesión de chat en Antigravity para hacer cambios mientras este opera:
1. **Acceso total a disco:** El segundo chat tiene acceso completo al directorio `C:\Users\Antonio Ramos\autonomous-micro-entrepreneur\`.
2. **Contexto:** Debe leer este archivo (`memoria/estado/SISTEMA_ACTUAL_HANDOVER.md`) y `memoria/estado/cola_oportunidades.json` para saber en qué estado está todo.
3. **Regla de concurrencia:** No debe matar procesos en ejecución a menos que el usuario lo pida explícitamente. `system_watchdog.py` reiniciará cualquier script caído.
4. **Cartera:** Toda solución debe incluir siempre `0x02c1F87F514493F359Afc0B3ff6b587434770361`.
