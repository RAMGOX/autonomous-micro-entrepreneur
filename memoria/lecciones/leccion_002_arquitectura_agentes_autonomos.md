# Lección 002: Arquitectura y Mejores Prácticas de Agentes Autónomos 24/7

- **Fecha:** 2026-10-22
- **Origen:** Análisis de repositorios líderes (`coinbase/agentkit`, `elizaos/eliza`, `goat-sdk`, `crawl4ai`).

---

## 1. Separación Estricta de Roles (The 4-Brain Pattern)
- **Error Clásico de Agentes:** Usar un único modelo grande (como GPT-4 o Claude 3.5) para todo. Resultado: Facturas de cientos de euros al mes y agotamiento de presupuesto en 48 horas.
- **Solución Adoptada:**
  - El 90% de las tareas operativas (escucha de Discord, monitoreo de procesos, formateo Markdown) corren en **Cerebro 1 (Ollama Qwen 2.5 local en GTX 1660)** a coste **0.00€**.
  - La planificación macro corre en **Cerebro 2 (Gemini Flash)**.
  - La programación y contratos corren en **Cerebro 3 (DeepSeek API)** con cuota diaria de 0.35€.
  - El arbitraje de seguridad corre en **Cerebro 4 (Argon)**.

---

## 2. Persistencia en Memoria de Archivo (Markdown First)
- Las bases de datos vectoriales pesadas suelen corromperse o consumir gigabytes de RAM.
- **Obsidian en Markdown** permite que tanto el agente como el usuario humano lean, editen y auditen exactamente el mismo estado sin herramientas complejas intermedias.

---

## 3. Resiliencia del Mando Remoto (Discord Bridge)
- Si el proceso del bot cae, un bucle supervisor (`Arrancar_Bot_Discord_24-7.bat`) lo resucita en 3 segundos.
- Los mensajes urgentes o preguntas del sistema se canalizan a `#general` con mención al usuario, permitiendo el control total desde el móvil sin estar delante del ordenador.
