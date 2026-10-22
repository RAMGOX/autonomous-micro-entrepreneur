# Solution: [BOUNTY $130] Databases Stack — Shared Multi-tenant PostgreSQL, Redis & MariaDB
- **Issue:** [illbnm/homelab-stack #11](https://github.com/illbnm/homelab-stack/issues/11)
- **Bounty:** $130 USDT
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Docker Compose Configuration (`stacks/databases/docker-compose.yml`)

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16.4-alpine
    container_name: db-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_SUPERUSER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_SUPERPASS:?required}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ../../scripts/init-databases.sh:/docker-entrypoint-initdb.d/init-databases.sh:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal
    ports:
      - "5432:5432"

  redis:
    image: redis:7.4.0-alpine
    container_name: db-redis
    restart: unless-stopped
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD:?required}"]
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD-SHELL", "redis-cli -a ${REDIS_PASSWORD} ping | grep PONG"]
      interval: 10s
      timeout: 3s
      retries: 5
    networks:
      - internal
    ports:
      - "6379:6379"

  mariadb:
    image: mariadb:11.5.2
    container_name: db-mariadb
    restart: unless-stopped
    environment:
      MARIADB_ROOT_PASSWORD: ${MARIADB_ROOT_PASS:?required}
    volumes:
      - mariadb-data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal
    ports:
      - "3306:3306"

  pgadmin:
    image: dpage/pgadmin4:8.11
    container_name: db-pgadmin
    restart: unless-stopped
    environment:
      PGADMIN_DEFAULT_EMAIL: ${ADMIN_EMAIL:-admin@homelab.local}
      PGADMIN_DEFAULT_PASSWORD: ${ADMIN_PASS:?required}
    volumes:
      - pgadmin-data:/var/lib/pgadmin
    networks:
      - internal
      - proxy
    ports:
      - "5050:80"

  redis-commander:
    image: rediscommander/redis-commander:latest
    container_name: db-redis-commander
    restart: unless-stopped
    environment:
      - REDIS_HOSTS=local:db-redis:6379:0:${REDIS_PASSWORD}
    networks:
      - internal
      - proxy
    ports:
      - "8081:8081"

volumes:
  postgres-data:
  redis-data:
  mariadb-data:
  pgadmin-data:

networks:
  internal:
    internal: true
  proxy:
    external: true
```

---

## 2. Idempotent Multi-Tenant Database Initialization (`scripts/init-databases.sh`)

```bash
#!/usr/bin/env bash
set -eo pipefail

create_db() {
    local db_name="$1"
    local db_pass="$2"

    echo "==> Provisioning database and user for: ${db_name}"
    psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" <<-EOSQL
        DO \$\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${db_name}') THEN
                CREATE ROLE ${db_name} WITH LOGIN PASSWORD '${db_pass}';
            END IF;
        END
        \$\$;

        SELECT 'CREATE DATABASE ${db_name} OWNER ${db_name}'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${db_name}')\gexec

        GRANT ALL PRIVILEGES ON DATABASE ${db_name} TO ${db_name};
EOSQL
}

create_db "nextcloud" "${NEXTCLOUD_DB_PASSWORD:-nextcloud_pass_123}"
create_db "gitea"     "${GITEA_DB_PASSWORD:-gitea_pass_123}"
create_db "outline"   "${OUTLINE_DB_PASSWORD:-outline_pass_123}"
create_db "authentik" "${AUTHENTIK_DB_PASSWORD:-authentik_pass_123}"
create_db "grafana"   "${GRAFANA_DB_PASSWORD:-grafana_pass_123}"
echo "==> All tenant databases verified."
```
