# Solution: [BOUNTY $100] HOOK: Pre-tool-use hook that blocks destructive bash commands
- **Issue:** [claude-builders-bounty/claude-builders-bounty #3](https://github.com/claude-builders-bounty/claude-builders-bounty/issues/3)
- **Bounty:** $100 USD (powered by Opire)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Python Pre-Tool-Use Hook (`~/.claude/hooks/pre-tool-use.py`)

```python
#!/usr/bin/env python3
"""
Claude Code Pre-Tool-Use Hook: Destructive Command Interceptor
Intercepts and blocks dangerous bash/SQL commands before execution.
Logs blocked actions to ~/.claude/hooks/blocked.log
"""

import sys
import json
import re
import os
from datetime import datetime
from pathlib import Path

LOG_FILE = Path.home() / ".claude" / "hooks" / "blocked.log"

DANGEROUS_PATTERNS = [
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|--recursive\s+--force|-[a-zA-Z]*f[a-zA-Z]*r)\b", "Recursive forced file deletion (rm -rf) is blocked."),
    (r"\bDROP\s+TABLE\b", "SQL DROP TABLE is blocked to prevent data destruction."),
    (r"\bgit\s+push\b.*\s+(-f|--force)\b", "Force-pushing git history (git push --force) is blocked."),
    (r"\bTRUNCATE(\s+TABLE)?\b", "SQL TRUNCATE is blocked to prevent data wiping."),
    (r"\bDELETE\s+FROM\s+[^\s;]+(?!\s+WHERE\b)[^;]*;", "Unconditional DELETE FROM without WHERE clause is blocked."),
]

def log_blocked(command: str, reason: str, cwd: str):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] BLOCKED: \"{command}\" | REASON: {reason} | CWD: {cwd}\n")

def main():
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    cwd = input_data.get("cwd", os.getcwd())

    if tool_name.lower() in ("bash", "shell", "run_command"):
        command = tool_input.get("command", "") or tool_input.get("CommandLine", "")

        for pattern, explanation in DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                log_blocked(command, explanation, cwd)
                # Output rejection message to Claude
                response = {
                    "decision": "reject",
                    "reason": f"SECURITY GUARDRAIL TRIGGERED: {explanation}\nAttempted: `{command}`\nLog recorded in: ~/.claude/hooks/blocked.log"
                }
                print(json.dumps(response))
                sys.exit(1)

    # Allow safe commands
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## 2. Unit Verification Test Suite (`tests/test_pre_tool_hook.py`)

```python
import json
import subprocess
import sys
from pathlib import Path

def run_hook_check(command_str: str) -> dict:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command_str},
        "cwd": "/workspace"
    }
    proc = subprocess.Popen(
        [sys.executable, "pre-tool-use.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, _ = proc.communicate(input=json.dumps(payload))
    return json.loads(stdout) if stdout else {"decision": "error"}

def test_guardrails():
    # Destructive tests
    assert run_hook_check("rm -rf /var/data")["decision"] == "reject"
    assert run_hook_check("git push origin main --force")["decision"] == "reject"
    assert run_hook_check("DROP TABLE users;")["decision"] == "reject"
    assert run_hook_check("TRUNCATE TABLE logs;")["decision"] == "reject"
    assert run_hook_check("DELETE FROM accounts;")["decision"] == "reject"

    # Safe commands
    assert run_hook_check("ls -la")["decision"] == "allow"
    assert run_hook_check("git push origin feature/test")["decision"] == "allow"
    assert run_hook_check("DELETE FROM accounts WHERE id = 5;")["decision"] == "allow"
    print("All security hook tests passed successfully!")

if __name__ == "__main__":
    test_guardrails()
```
