# Estrategia 03: Arquitectura AgentKit y Gestión de Gas en Base Sepolia

- **Objetivo:** Operaciones autónomas en cadena con la cartera `0x02c1F87F514493F359Afc0B3ff6b587434770361`.
- **Red:** Base Sepolia Testnet (Chain ID `84532`).
- **Framework de Referencia:** `coinbase/agentkit` y `goat-sdk/goat`.

---

## 1. Principios de Operación en Red de Prueba (Días 1 a 7)
1. **Regla de Cero Riesgo:** Todos los tokens operados son ficticios (Testnet ETH).
2. **Ciclo de Reabastecimiento de Gas (Faucets):**
   - El agente verifica su balance de ETH mediante llamadas RPC a `https://sepolia.base.org`.
   - Si el balance es inferior a `0.005 ETH`, genera una alerta en Discord solicitando el reclamo de faucet o ejecuta los scripts de faucet automatizados.
3. **Acciones On-chain Autónomas Permitidas:**
   - Despliegue de contratos de prueba ERC-20 / ERC-721 en Base Sepolia.
   - Interacción con contratos de oráculos (precios de activos via Chainlink / Pyth).
   - Firma y verificación de transacciones mediante clave local cifrada en `.env`.

---

## 2. Guardrails de Seguridad (Protección Contra Pérdidas)
- **Tope de Gas:** Máximo 50 Gwei por transacción de prueba.
- **Circuit Breaker:** Si 3 transacciones consecutivas fallan, se detiene la ejecución on-chain durante 2 horas y se anota el error en `/memoria/lecciones/`.
- **Aislamiento de Llave Privada:** La clave privada nunca se imprime en logs, nunca se envía por Discord y nunca entra en los prompts enviados a los modelos de lenguaje.
