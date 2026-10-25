# 🧠 Prompts para Chats Paralelos de Gemini Pro (Coste API: 0,00 €)

Usa estos prompts en nuevas conversaciones de **Antigravity / Gemini Pro** con bucles automáticos (`/schedule` o `/goal`). Todos escriben sus entregas directamente en `memoria/estado/bandeja_revision.json` mediante `src/review_queue.py`, de modo que **te llegarán al móvil por Discord con botones de Aprobar / Ver / Editar / Descartar**.

---

## 🎯 CHAT PARALELO 1: Ingeniero Resolutor de Bounties GitHub / Algora (Bucle cada 4 horas)

> **Cuándo usarlo:** Déjalo corriendo en un chat paralelo con `/schedule` cada 4 horas (`0 */4 * * *`). Aprovecha la potencia máxima de tu cuenta Gemini Pro para clonar repositorios, ejecutar tests reales y dejar parches listos sin gastar saldo de DeepSeek.

```text
Trabaja sobre el repositorio `C:\Users\Antonio Ramos\autonomous-micro-entrepreneur` usando el entorno Python `C:\Users\Antonio Ramos\autonomous-micro-entrepreneur\.venv\Scripts\python.exe`.

Configura un ciclo recurrente cada 4 horas (`0 */4 * * *`) y ejecuta también la primera pasada ahora mismo siguiendo estas reglas estrictas:

1. ACTUALIZAR COLA REAL:
   - Ejecuta `src/github_bounty_hunter.py` para refrescar bounties abiertas en USD ($25-$3,000) sin asignatario (`no:assignee`).
   - Lee `memoria/estado/cola_oportunidades.json` y `memoria/MOTOR_1_BOUNTIES_GITHUB.md`.

2. SELECCIONAR LA MEJOR OPORTUNIDAD TÉCNICA:
   - Elige 1 issue con `"status": "pending"` y `"source": "github_bounty"` donde el problema sea reproducible en Python, TypeScript/JS, Rust o Go y tenga criterios de aceptación claros.
   - Si ya está en `memoria/estado/bandeja_revision.json`, sáltala.

3. RESOLUCIÓN REAL CON TESTS (CERO HUMO):
   - Haz shallow clone (`git clone --depth 1`) del repositorio objetivo dentro de `workspace_bounties/<repo_issue_id>/`.
   - Lee el issue completo y los archivos afectados.
   - Implementa la solución mínima, limpia y quirúrgica siguiendo el estilo del repo.
   - Ejecuta los tests del proyecto o un script de verificación real que demuestre que el fix funciona al 100%. Si no puedes verificarlo o falta contexto externo/credenciales privadas, descarta esa issue marcándola `"status": "skipped_unverifiable"` en `cola_oportunidades.json` y pasa a otra.

4. PREPARAR ENTREGA PARA APROBACIÓN MÓVIL EN DISCORD (PROHIBIDO ABRIR PR O COMENTAR SIN PERMISO):
   - Guarda en `memoria/soluciones_preparadas/pr_ready_<repo>_<issue>.md` el parche unificado (`git diff`), resultado literal de los tests ejecutados y el texto breve y profesional para el Pull Request.
   - Registra la entrega llamando a `push_for_review(...)` de `src/review_queue.py` con:
     - `category="github_bounty"`
     - `deliverable_path="memoria/soluciones_preparadas/pr_ready_<repo>_<issue>.md"`
     - `solver="Gemini Pro (Chat Paralelo)"`
   - Marca la oportunidad como `"status": "in_review"` en `cola_oportunidades.json`.
   - El bot de Discord enviará automáticamente los botones interactivos al móvil de Antonio.
```

---

## 🕷️ CHAT PARALELO 2: Fábrica y Mejora Continua de Actores Apify / MCP & x402 (Bucle cada 8 horas)

> **Cuándo usarlo:** Segundo chat paralelo en bucle cada 8 horas (`0 */8 * * *`) enfocado en ingresos recurrentes B2B (Apify Store Pay-Per-Event + MCP Servers + endpoints x402).

```text
Trabaja sobre `C:\Users\Antonio Ramos\autonomous-micro-entrepreneur` usando `C:\Users\Antonio Ramos\autonomous-micro-entrepreneur\.venv\Scripts\python.exe`.

Configura un ciclo cada 8 horas (`0 */8 * * *`) y ejecuta una pasada inicial ahora:

1. AUDITORÍA DE SALUD DE MOTORES Y COSTE:
   - Revisa `memoria/estado/deepseek_presupuesto.json` (verificar que nunca supere `0.50 €/día`), `memoria/estado/apify_actors_status.json`, `memoria/estado/x402_ventas.json` y los últimos errores en `logs/autonomous_daemon.log`.
   - Si detectas un bug real en `src/`, corrígelo quirúrgicamente y verifícalo con test.

2. MEJORAR Y AMPLIAR ACTORES APIFY / MCP (`apify_actors/`):
   - Ejecuta `src/apify_actor_factory.py` para validar con datos reales los actores existentes (`eu-public-tenders-b2b`, `base-dex-rug-auditor`).
   - Investiga nichos B2B de alta demanda y baja competencia para agentes IA / MCP (datos públicos gubernamentales, registros mercantiles, auditoría técnica Web3, validación de leads) que funcionen sin proxies de pago ni APIs de pago.
   - Si diseñas o mejoras sustancialmente un Actor (con `.actor/actor.json`, `input_schema.json`, `README.md` comercial orientado a SEO y `src/main.py --smoke-test` pasando con datos reales), regístralo con `push_for_review(category="apify_actor", ...)` en `src/review_queue.py` para que Antonio lo revise y apruebe desde Discord en el móvil.

3. HIGIENE DE OBSIDIAN:
   - Mantén actualizados `memoria/MOTOR_2_APIFY_ACTORS.md` y `memoria/CEREBRO_CENTRAL.md` con datos verificados, sin borrar historial útil.
```

---

## 🚀 CHAT PUNTUAL (Bajo Demanda): Publicar un PR ya aprobado por ti en Discord

> **Cuándo usarlo:** Cuando pulses **✅ Aprobar** en una entrega de GitHub Bounty desde tu móvil y quieras que un chat de Gemini Pro suba el fork + Pull Request limpio.

```text
En `C:\Users\Antonio Ramos\autonomous-micro-entrepreneur`, revisa `memoria/estado/bandeja_revision.json` y busca las entregas con `"category": "github_bounty"` y `"status": "approved"`.

Para cada entrega aprobada por Antonio:
1. Verifica que el clon en `workspace_bounties/` o el parche en `deliverable_path` aplica limpio sobre la rama principal actualizada del repositorio upstream y que los tests siguen pasando.
2. Verifica en GitHub que el issue sigue abierto y sin otro PR ganador fusionado.
3. Usa `GITHUB_TOKEN` de `config/.env` para hacer fork en la cuenta de Antonio, subir la rama del fix y abrir el Pull Request siguiendo exactamente la plantilla del repositorio (incluyendo `Closes #<issue>` / `/claim #<issue>` si es Algora).
4. Actualiza la entrega en `bandeja_revision.json` a `"status": "sent"` con el enlace real del PR creado y avisa por Discord usando `notify_user_discord` de `src/discord_bridge.py`.
```
