# Solution: [BOUNTY $300] SSO — Authentik 统一身份认证
- **Issue:** [illbnm/homelab-stack #9](https://github.com/illbnm/homelab-stack/issues/9)
- **Bounty:** $300 USDT
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Docker Compose Configuration (`stacks/sso/docker-compose.yml`)

```yaml
version: '3.8'

services:
  authentik-postgresql:
    image: postgres:16.4-alpine
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d $${POSTGRES_DB} -U $${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: ${PG_PASS:?error}
      POSTGRES_USER: ${PG_USER:-authentik}
      POSTGRES_DB: ${PG_DB:-authentik}
    networks:
      - internal

  authentik-redis:
    image: redis:7.4.0-alpine
    command: --save 60 1 --loglevel warning
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "redis-cli ping | grep PONG"]
      interval: 10s
      timeout: 3s
      retries: 5
    volumes:
      - redis-data:/data
    networks:
      - internal

  authentik-server:
    image: ghcr.io/goauthentik/server:2024.8.3
    restart: unless-stopped
    command: server
    environment:
      AUTHENTIK_REDIS__HOST: authentik-redis
      AUTHENTIK_POSTGRESQL__HOST: authentik-postgresql
      AUTHENTIK_POSTGRESQL__USER: ${PG_USER:-authentik}
      AUTHENTIK_POSTGRESQL__NAME: ${PG_DB:-authentik}
      AUTHENTIK_POSTGRESQL__PASSWORD: ${PG_PASS}
      AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY}
      AUTHENTIK_ERROR_REPORTING__ENABLED: "false"
      AUTHENTIK_BOOTSTRAP_PASSWORD: ${AUTHENTIK_BOOTSTRAP_PASSWORD}
      AUTHENTIK_BOOTSTRAP_EMAIL: admin@${DOMAIN}
    volumes:
      - ./media:/media
      - ./custom-templates:/templates
    ports:
      - "9000:9000"
      - "9443:9443"
    depends_on:
      authentik-postgresql:
        condition: service_healthy
      authentik-redis:
        condition: service_healthy
    networks:
      - internal
      - proxy

  authentik-worker:
    image: ghcr.io/goauthentik/server:2024.8.3
    restart: unless-stopped
    command: worker
    environment:
      AUTHENTIK_REDIS__HOST: authentik-redis
      AUTHENTIK_POSTGRESQL__HOST: authentik-postgresql
      AUTHENTIK_POSTGRESQL__USER: ${PG_USER:-authentik}
      AUTHENTIK_POSTGRESQL__NAME: ${PG_DB:-authentik}
      AUTHENTIK_POSTGRESQL__PASSWORD: ${PG_PASS}
      AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./media:/media
      - ./certs:/certs
      - ./custom-templates:/templates
    depends_on:
      authentik-postgresql:
        condition: service_healthy
      authentik-redis:
        condition: service_healthy
    networks:
      - internal

volumes:
  postgres-data:
  redis-data:

networks:
  internal:
    internal: true
  proxy:
    external: true
```

---

## 2. OIDC Provider Configurations for Connected Services

### A. Grafana (`config/grafana/grafana.ini`)
```ini
[auth.generic_oauth]
enabled = true
name = Authentik
allow_sign_up = true
client_id = grafana
client_secret = ${GRAFANA_OIDC_SECRET}
scopes = openid profile email
auth_url = https://auth.${DOMAIN}/application/o/authorize/
token_url = https://auth.${DOMAIN}/application/o/token/
api_url = https://auth.${DOMAIN}/application/o/userinfo/
role_attribute_path = contains(groups[*], 'grafana-admins') && 'Admin' || contains(groups[*], 'grafana-editors') && 'Editor' || 'Viewer'
```

### B. Gitea (`stacks/productivity/.env`)
```env
# Authentik OIDC Auth source for Gitea
GITEA__oauth2_client__ENABLE=true
GITEA__oauth2_client__ACCOUNT_LINKING=auto
GITEA__oauth2_client__OPENID_CONNECT_SCOPES=openid profile email
# Gitea CLI registration command:
# gitea admin auth add-oauth --name Authentik --provider openidConnect --key gitea --secret ${GITEA_OIDC_SECRET} --auto-discover-url https://auth.${DOMAIN}/application/o/gitea/.well-known/openid-configuration
```

### C. Nextcloud (`scripts/nextcloud-oidc-setup.sh`)
```bash
#!/bin/bash
set -euo pipefail

docker compose exec -u www-data nextcloud-app php occ app:enable user_oidc
docker compose exec -u www-data nextcloud-app php occ user_oidc:provider \
  authentik \
  --clientid="nextcloud" \
  --clientsecret="${NEXTCLOUD_OIDC_SECRET}" \
  --discoveryuri="https://auth.${DOMAIN}/application/o/nextcloud/.well-known/openid-configuration" \
  --scope="openid profile email" \
  --unique-uid=1
echo "Nextcloud Authentik OIDC setup successfully completed."
```

### D. Outline Knowledge Base (`stacks/productivity/.env`)
```env
OIDC_CLIENT_ID=outline
OIDC_CLIENT_SECRET=${OUTLINE_OIDC_SECRET}
OIDC_AUTH_URI=https://auth.${DOMAIN}/application/o/authorize/
OIDC_TOKEN_URI=https://auth.${DOMAIN}/application/o/token/
OIDC_USERINFO_URI=https://auth.${DOMAIN}/application/o/userinfo/
OIDC_DISPLAY_NAME=Authentik SSO
OIDC_SCOPES=openid profile email
```

### E. Open WebUI (`stacks/ai/.env`)
```env
ENABLE_OAUTH_SIGNUP=True
OAUTH_CLIENT_ID=openwebui
OAUTH_CLIENT_SECRET=${OPENWEBUI_OIDC_SECRET}
OPENID_PROVIDER_URL=https://auth.${DOMAIN}/application/o/openwebui/.well-known/openid-configuration
OAUTH_PROVIDER_NAME=Authentik
OAUTH_SCOPES=openid profile email
```
