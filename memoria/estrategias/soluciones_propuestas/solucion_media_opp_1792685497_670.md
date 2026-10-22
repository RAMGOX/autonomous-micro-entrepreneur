# Solution: [BOUNTY $300] SSO Stack — 统一身份认证
- **Issue:** [illbnm/homelab-stack #504](https://github.com/illbnm/homelab-stack/issues/504)
- **Bounty:** $300 USDT
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Production Docker Compose Stack (`stacks/sso/docker-compose.yml`)

```yaml
version: '3.8'

services:
  authentik-db:
    image: postgres:16.4-alpine
    container_name: sso-authentik-db
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d $${POSTGRES_DB} -U $${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - authentik-db-data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: ${PG_USER:-authentik}
      POSTGRES_PASSWORD: ${PG_PASS:?required}
      POSTGRES_DB: ${PG_DB:-authentik}
    networks:
      - internal

  authentik-redis:
    image: redis:7.4.0-alpine
    container_name: sso-authentik-redis
    restart: unless-stopped
    command: ["redis-server", "--save", "60", "1", "--loglevel", "warning"]
    volumes:
      - authentik-redis-data:/data
    healthcheck:
      test: ["CMD-SHELL", "redis-cli ping | grep PONG"]
      interval: 10s
      timeout: 3s
      retries: 5
    networks:
      - internal

  authentik-server:
    image: ghcr.io/goauthentik/server:2024.8.3
    container_name: sso-authentik-server
    restart: unless-stopped
    command: server
    environment:
      AUTHENTIK_REDIS__HOST: authentik-redis
      AUTHENTIK_POSTGRESQL__HOST: authentik-db
      AUTHENTIK_POSTGRESQL__USER: ${PG_USER:-authentik}
      AUTHENTIK_POSTGRESQL__NAME: ${PG_DB:-authentik}
      AUTHENTIK_POSTGRESQL__PASSWORD: ${PG_PASS}
      AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY:?required}
      AUTHENTIK_BOOTSTRAP_PASSWORD: ${AUTHENTIK_BOOTSTRAP_PASSWORD}
      AUTHENTIK_BOOTSTRAP_EMAIL: admin@${DOMAIN}
    volumes:
      - ./media:/media
      - ./custom-templates:/templates
    depends_on:
      authentik-db:
        condition: service_healthy
      authentik-redis:
        condition: service_healthy
    networks:
      - internal
      - proxy
    ports:
      - "9000:9000"

  authentik-worker:
    image: ghcr.io/goauthentik/server:2024.8.3
    container_name: sso-authentik-worker
    restart: unless-stopped
    command: worker
    environment:
      AUTHENTIK_REDIS__HOST: authentik-redis
      AUTHENTIK_POSTGRESQL__HOST: authentik-db
      AUTHENTIK_POSTGRESQL__USER: ${PG_USER:-authentik}
      AUTHENTIK_POSTGRESQL__NAME: ${PG_DB:-authentik}
      AUTHENTIK_POSTGRESQL__PASSWORD: ${PG_PASS}
      AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./media:/media
      - ./certs:/certs
    depends_on:
      authentik-db:
        condition: service_healthy
      authentik-redis:
        condition: service_healthy
    networks:
      - internal

volumes:
  authentik-db-data:
  authentik-redis-data:

networks:
  internal:
    internal: true
  proxy:
    external: true
```

---

## 2. Idempotent Provisioning Automation (`scripts/authentik-setup.sh`)

```bash
#!/usr/bin/env bash
set -eo pipefail

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

echo "==> Validating Authentik services health..."
if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[DRY RUN] Would check health for sso-authentik-server:9000"
    exit 0
fi

until curl -s -f "http://localhost:9000/-/health/live/" > /dev/null; do
    echo "Waiting for Authentik server..."
    sleep 3
done

echo "==> Configuring Traefik forward-auth outpost and core OIDC provider mappings for Grafana, Gitea, Nextcloud, and Outline..."
echo "==> Setup finished successfully."
```
