# Solution: [BOUNTY $220] AI Stack — Ollama + Open WebUI + Stable Diffusion + Perplexica
- **Issue:** [illbnm/homelab-stack #6](https://github.com/illbnm/homelab-stack/issues/6)
- **Bounty:** $220 USDT
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Docker Compose Configuration (`stacks/ai/docker-compose.yml`)

```yaml
version: '3.8'

services:
  ollama:
    image: ollama/ollama:0.3.12
    container_name: ai-ollama
    restart: unless-stopped
    volumes:
      - ollama-models:/root/.ollama
    environment:
      - OLLAMA_KEEP_ALIVE=24h
      - OLLAMA_HOST=0.0.0.0:11434
    networks:
      - internal
      - proxy
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 15s
      timeout: 10s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  open-webui:
    image: ghcr.io/open-webui/open-webui:0.3.32
    container_name: ai-open-webui
    restart: unless-stopped
    depends_on:
      ollama:
        condition: service_healthy
    volumes:
      - open-webui-data:/app/backend/data
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY:-homelab-secret-key-32chars}
      - ENABLE_IMAGE_GENERATION=True
      - IMAGE_GENERATION_ENGINE=automatic1111
      - AUTOMATIC1111_BASE_URL=http://stable-diffusion:7860
    networks:
      - internal
      - proxy
    ports:
      - "3000:8080"

  stable-diffusion:
    image: universonic/stable-diffusion-webui:latest-sha
    container_name: ai-stable-diffusion
    restart: unless-stopped
    environment:
      - CLI_ARGS=--listen --api --enable-insecure-extension-access --opt-sdp-attention
    volumes:
      - sd-models:/app/stable-diffusion-webui/models
      - sd-outputs:/app/stable-diffusion-webui/outputs
    networks:
      - internal
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  perplexica:
    image: itzcrazykns1337/perplexica:main-sha
    container_name: ai-perplexica
    restart: unless-stopped
    depends_on:
      ollama:
        condition: service_healthy
    environment:
      - SEARXNG_API_URL=http://searxng:8080
      - OLLAMA_API_URL=http://ollama:11434
    networks:
      - internal
      - proxy
    ports:
      - "3001:3000"

volumes:
  ollama-models:
  open-webui-data:
  sd-models:
  sd-outputs:

networks:
  internal:
    internal: true
  proxy:
    external: true
```

---

## 2. Model Auto-Provisioning Script (`scripts/preload-ai-models.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> Waiting for Ollama service to become healthy..."
until docker exec ai-ollama ollama list >/dev/null 2>&1; do
    sleep 3
done

MODELS=("qwen2.5-coder:7b" "llama3.1:8b" "nomic-embed-text")
for model in "${MODELS[@]}"; do
    echo "==> Pulling model: ${model}..."
    docker exec ai-ollama ollama pull "${model}"
done

echo "==> Preloading finished. AI stack is fully operational."
```
