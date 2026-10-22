# Solution: fix(agents): robust host port extraction for bind-IP and IPv6 port mappings
- **Repository:** `PayRam/payram-scripts`
- **Issue:** [#108](https://github.com/PayRam/payram-scripts/issues/108)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Problem Analysis & Root Cause

In `setup_payram_agents.sh` (around line 228), `load_install_config` derives the agent's target API URL by parsing port token strings from `RETAINED_PORTS`:

```bash
local tok host cont http_port="" https_port=""
for tok in $retained_ports; do
    tok="${tok%%/*}"
    host="${tok%%:*}"
    cont="${tok##*:}"
    [[ "$cont" == "80" && -z "$http_port" ]] && http_port="$host"
    [[ "$cont" == "443" && -z "$https_port" ]] && https_port="$host"
done
```

### The Bug
`host="${tok%%:*}"` strips everything after the **first** colon.
- For standard `8080:80`, `host` correctly evaluates to `8080`.
- For Docker bind-IP port mappings such as `127.0.0.1:8080:80` (created when the installer binds to a specific interface), `tok%%:*` evaluates to `127.0.0.1`.
- For IPv6 loopback bindings such as `[::1]:8080:80`, `tok%%:*` evaluates to `[`.
- Downstream call `localhost_url http "$http_port" 80` then constructs malformed URLs like `http://localhost:127.0.0.1` or `http://localhost:[` rather than `http://localhost:8080`.

---

## 2. Surgical Code Patch (`setup_payram_agents.sh`)

By trimming the trailing container port (`${tok%:*}`) first and extracting the port from the remaining segment (`${host_part##*:}`), the host port is extracted reliably regardless of whether an IPv4 or IPv6 bind address prefix is present:

```diff
--- a/setup_payram_agents.sh
+++ b/setup_payram_agents.sh
@@ -226,8 +226,9 @@ load_install_config() {
 	local tok host cont http_port="" https_port=""
 	for tok in $retained_ports; do
 		tok="${tok%%/*}"
-		host="${tok%%:*}"
+		local host_part="${tok%:*}"
+		host="${host_part##*:}"
 		cont="${tok##*:}"
 		[[ "$cont" == "80" && -z "$http_port" ]] && http_port="$host"
 		[[ "$cont" == "443" && -z "$https_port" ]] && https_port="$host"
 	done
```

---

## 3. Hermetic Test & Validation Suite

```bash
#!/usr/bin/env bash
set -euo pipefail

parse_ports() {
    local retained_ports="$1"
    local tok host cont http_port="" https_port=""
    for tok in $retained_ports; do
        tok="${tok%%/*}"
        local host_part="${tok%:*}"
        host="${host_part##*:}"
        cont="${tok##*:}"
        [[ "$cont" == "80" && -z "$http_port" ]] && http_port="$host"
        [[ "$cont" == "443" && -z "$https_port" ]] && https_port="$host"
    done
    echo "http:${http_port:-none}|https:${https_port:-none}"
}

# Test cases
test_mapping() {
    local input="$1"
    local expected="$2"
    local result
    result=$(parse_ports "$input")
    if [[ "$result" == "$expected" ]]; then
        echo "[PASS] '$input' -> '$result'"
    else
        echo "[FAIL] '$input' -> expected '$expected', got '$result'"
        exit 1
    fi
}

echo "Running Port Derivation Tests:"
test_mapping "8080:80" "http:8080|https:none"
test_mapping "127.0.0.1:8080:80" "http:8080|https:none"
test_mapping "[::1]:8080:80" "http:8080|https:none"
test_mapping "192.168.1.100:8443:443" "http:none|https:8443"
test_mapping "127.0.0.1:8080:80 127.0.0.1:8443:443" "http:8080|https:8443"
test_mapping "80:80/tcp 443:443/tcp" "http:80|https:443"

echo "All 6 test cases passed cleanly."
```
Suite results: 6/6 tests pass without requiring external network dependencies or Docker daemons.
