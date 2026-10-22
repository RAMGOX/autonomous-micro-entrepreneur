# Solution: [BOUNTY $80] Notifications Stack — ntfy + Gotify + notify.sh
- **Issue:** [illbnm/homelab-stack #13](https://github.com/illbnm/homelab-stack/issues/13)
- **Bounty:** $80 USDT
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Docker Compose Configuration (`stacks/notifications/docker-compose.yml`)

```yaml
version: '3.8'

services:
  ntfy:
    image: binwiederhier/ntfy:v2.11.0
    container_name: notify-ntfy
    restart: unless-stopped
    command: serve
    environment:
      - TZ=UTC
    volumes:
      - ../../config/ntfy/server.yml:/etc/ntfy/server.yml:ro
      - ntfy-cache:/var/cache/ntfy
      - ntfy-data:/var/lib/ntfy
    networks:
      - internal
      - proxy
    ports:
      - "8082:80"

  gotify:
    image: gotify/server:2.5.0
    container_name: notify-gotify
    restart: unless-stopped
    environment:
      - GOTIFY_DEFAULTUSER_NAME=admin
      - GOTIFY_DEFAULTUSER_PASS=${GOTIFY_ADMIN_PASS:-gotify_secure_pass}
    volumes:
      - gotify-data:/app/data
    networks:
      - internal
      - proxy
    ports:
      - "8083:80"

volumes:
  ntfy-cache:
  ntfy-data:
  gotify-data:

networks:
  internal:
    internal: true
  proxy:
    external: true
```

---

## 2. Server Configuration (`config/ntfy/server.yml`)

```yaml
base-url: https://ntfy.${DOMAIN}
listen-http: ":80"
behind-proxy: true
auth-default-access: "deny-all"
cache-file: "/var/cache/ntfy/cache.db"
auth-file: "/var/lib/ntfy/user.db"
attachment-cache-dir: "/var/cache/ntfy/attachments"
```

---

## 3. Universal Notification CLI Script (`scripts/notify.sh`)

```bash
#!/usr/bin/env bash
set -eo pipefail

TOPIC="${1:?Error: topic required}"
TITLE="${2:?Error: title required}"
MESSAGE="${3:?Error: message required}"
PRIORITY="${4:-3}" # 1=min, 3=default, 5=urgent
TAGS="${5:-bell}"

NTFY_URL="${NTFY_BASE_URL:-http://localhost:8082}"
NTFY_TOKEN="${NTFY_TOKEN:-}"

AUTH_HEADER=()
if [[ -n "${NTFY_TOKEN}" ]]; then
    AUTH_HEADER=(-H "Authorization: Bearer ${NTFY_TOKEN}")
fi

curl -s -X POST "${NTFY_URL}/${TOPIC}" \
  -H "Title: ${TITLE}" \
  -H "Priority: ${PRIORITY}" \
  -H "Tags: ${TAGS}" \
  "${AUTH_HEADER[@]}" \
  -d "${MESSAGE}"

echo "Notification sent to ${TOPIC}."
```

---

## 4. Ecosystem Integration Configs (`stacks/notifications/README.md`)

- **Alertmanager:** Add webhook receiver to `http://notify-ntfy:80/alerts`.
- **Watchtower:** Set `WATCHTOWER_NOTIFICATION_URL=ntfy://notify-ntfy:80/watchtower`.
- **Gitea:** Webhook target `http://notify-ntfy:80/gitea-events` with payload POST.
- **Home Assistant:** Add `notify.rest` service pointing to `http://notify-ntfy:80/homeassistant`.
- **Uptime Kuma:** Channel `ntfy` with Server URL `http://notify-ntfy:80` and Topic `uptime`.
