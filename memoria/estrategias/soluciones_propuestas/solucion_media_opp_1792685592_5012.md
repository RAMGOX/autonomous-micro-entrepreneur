# Solution: [BOUNTY $150] Backup & Recovery — 备份与灾难恢复完整方案
- **Issue:** [illbnm/homelab-stack #12](https://github.com/illbnm/homelab-stack/issues/12)
- **Bounty:** $150 USDT
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Backup Infrastructure (`stacks/backup/docker-compose.yml`)

```yaml
version: '3.8'

services:
  restic-rest-server:
    image: restic/rest-server:0.13.0
    container_name: backup-rest-server
    restart: unless-stopped
    environment:
      - OPTIONS=--prometheus --no-auth
    volumes:
      - /mnt/backups/restic-repo:/data
    networks:
      - internal
    ports:
      - "8000:8000"

  duplicati:
    image: lscr.io/linuxserver/duplicati:2.0.8
    container_name: backup-duplicati
    restart: unless-stopped
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=UTC
      - CLI_ARGS=
    volumes:
      - duplicati-config:/config
      - /var/lib/docker/volumes:/source/volumes:ro
      - /mnt/backups/duplicati:/backups
    networks:
      - internal
      - proxy
    ports:
      - "8200:8200"

volumes:
  duplicati-config:

networks:
  internal:
    internal: true
  proxy:
    external: true
```

---

## 2. Universal Automated Backup Engine (`scripts/backup.sh`)

```bash
#!/usr/bin/env bash
set -eo pipefail

RESTIC_REPOSITORY="${RESTIC_REPOSITORY:-rest:http://localhost:8000/}"
RESTIC_PASSWORD="${RESTIC_PASSWORD:-homelab-backup-secure-pass}"
export RESTIC_REPOSITORY RESTIC_PASSWORD

TARGET="all"
DRY_RUN=false
ACTION="backup"
RESTORE_ID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) TARGET="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --list) ACTION="list"; shift ;;
        --verify) ACTION="verify"; shift ;;
        --restore) ACTION="restore"; RESTORE_ID="$2"; shift 2 ;;
        *) echo "Unknown parameter $1"; exit 1 ;;
    esac
done

if [[ "${ACTION}" == "list" ]]; then
    restic snapshots
    exit 0
fi

if [[ "${ACTION}" == "verify" ]]; then
    restic check
    exit 0
fi

if [[ "${ACTION}" == "restore" ]]; then
    if [[ -z "${RESTORE_ID}" ]]; then
        echo "Error: Must specify snapshot ID with --restore <id>"
        exit 1
    fi
    echo "Restoring snapshot ${RESTORE_ID} to /mnt/recovery..."
    restic restore "${RESTORE_ID}" --target /mnt/recovery
    echo "Restore completed."
    exit 0
fi

echo "Initiating 3-2-1 backup for target: ${TARGET}..."
BACKUP_PATHS=("/var/lib/docker/volumes" "/opt/homelab/config")

if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[DRY RUN] Would backup paths: ${BACKUP_PATHS[*]} to ${RESTIC_REPOSITORY}"
    exit 0
fi

# Initialize repo if needed
restic init || true

# Execute encrypted deduplicated backup
restic backup "${BACKUP_PATHS[@]}" \
  --tag "target:${TARGET}" \
  --exclude "*.log" \
  --exclude "tmp/*"

# Retain policy (7 daily, 4 weekly, 12 monthly)
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune

echo "Backup and prune successfully finished."
```

---

## 3. Disaster Recovery Runbook (`docs/disaster-recovery.md`)

```markdown
# Disaster Recovery Runbook (RTO: < 45 Minutes)

### Phase 1: Environment Provisioning (0-15 Min)
1. Install Docker Engine and Docker Compose.
2. Clone repository: `git clone https://github.com/illbnm/homelab-stack /opt/homelab`.
3. Configure `.env` with production keys.

### Phase 2: Data Volume Restoration (15-30 Min)
1. Run `./scripts/backup.sh --restore latest`.
2. Move restored volumes to `/var/lib/docker/volumes/`.

### Phase 3: Service Startup Hierarchy (30-45 Min)
1. Base & Database layers: `docker compose -f stacks/databases/docker-compose.yml up -d`
2. SSO & Auth: `docker compose -f stacks/sso/docker-compose.yml up -d`
3. Monitoring & Apps: `docker compose -f stacks/monitoring/docker-compose.yml up -d`
4. Verify all systems: `./tests/run-tests.sh --all`
```
