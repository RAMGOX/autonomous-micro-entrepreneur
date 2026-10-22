# Solution: [BOUNTY $280] Integration Testing — Automated Integration Testing Suite
- **Issue:** [illbnm/homelab-stack #14](https://github.com/illbnm/homelab-stack/issues/14)
- **Bounty:** $280 USDT
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Test Harness Entrypoint (`tests/run-tests.sh`)

```bash
#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/assert.sh"
source "${SCRIPT_DIR}/lib/docker.sh"
source "${SCRIPT_DIR}/lib/report.sh"

TARGET_STACK="${1:---all}"
report_init

run_stack_test() {
    local stack_file="$1"
    local stack_name
    stack_name="$(basename "${stack_file}" .test.sh)"
    echo -e "\n\033[1;34m[TEST SUITE]\033[0m Running tests for stack: ${stack_name}"
    bash "${stack_file}"
}

if [[ "${TARGET_STACK}" == "--all" ]]; then
    for test_script in "${SCRIPT_DIR}"/stacks/*.test.sh; do
        if [[ -f "${test_script}" ]]; then
            run_stack_test "${test_script}"
        fi
    done
else
    TARGET_FILE="${SCRIPT_DIR}/stacks/${TARGET_STACK}.test.sh"
    if [[ -f "${TARGET_FILE}" ]]; then
        run_stack_test "${TARGET_FILE}"
    else
        echo -e "\033[1;31m[ERROR]\033[0m Test file ${TARGET_FILE} not found."
        exit 1
    fi
fi

report_summary
```

---

## 2. Core Assertion Library (`tests/lib/assert.sh`)

```bash
#!/usr/bin/env bash

assert_container_running() {
    local container="$1"
    local status
    status="$(docker inspect --format '{{.State.Status}}' "${container}" 2>/dev/null || echo "missing")"
    if [[ "${status}" == "running" ]]; then
        record_pass "Container ${container} is running."
    else
        record_fail "Container ${container} expected 'running', got '${status}'."
    fi
}

assert_container_healthy() {
    local container="$1"
    local health
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${container}" 2>/dev/null || echo "missing")"
    if [[ "${health}" == "healthy" || "${health}" == "none" ]]; then
        record_pass "Container ${container} healthcheck status: ${health}."
    else
        record_fail "Container ${container} healthcheck unhealthy: '${health}'."
    fi
}

assert_http_status() {
    local url="$1"
    local expected="${2:-200}"
    local code
    code="$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${url}" || echo "000")"
    if [[ "${code}" == "${expected}" ]]; then
        record_pass "HTTP ${url} returned expected status ${expected}."
    else
        record_fail "HTTP ${url} expected ${expected}, got ${code}."
    fi
}
```

---

## 3. Reporting Utilities (`tests/lib/report.sh`)

```bash
#!/usr/bin/env bash

PASSED_COUNT=0
FAILED_COUNT=0

report_init() {
    PASSED_COUNT=0
    FAILED_COUNT=0
}

record_pass() {
    local msg="$1"
    ((PASSED_COUNT++))
    echo -e "  \033[32m✔ PASS\033[0m: ${msg}"
}

record_fail() {
    local msg="$1"
    ((FAILED_COUNT++))
    echo -e "  \033[31m✘ FAIL\033[0m: ${msg}"
}

report_summary() {
    echo -e "\n=========================================="
    echo -e "\033[1mTEST EXECUTION SUMMARY\033[0m"
    echo -e "  Passed: \033[32m${PASSED_COUNT}\033[0m"
    echo -e "  Failed: \033[31m${FAILED_COUNT}\033[0m"
    echo -e "=========================================="
    if [[ ${FAILED_COUNT} -gt 0 ]]; then
        exit 1
    fi
}
```

---

## 4. Stack Test Suite Example (`tests/stacks/monitoring.test.sh`)

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${SCRIPT_DIR}/lib/assert.sh"

assert_container_running "monitoring-prometheus"
assert_container_healthy "monitoring-prometheus"
assert_http_status "http://localhost:9090/-/healthy" 200

assert_container_running "monitoring-grafana"
assert_http_status "http://localhost:3000/api/health" 200

assert_container_running "monitoring-loki"
assert_http_status "http://localhost:3100/ready" 200
```
