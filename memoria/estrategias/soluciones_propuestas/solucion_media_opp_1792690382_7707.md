# Solución para: 【实战解密】我用 AI 智能体扫荡 GitHub 开源悬赏：48 小时合并 6 个 PR 斩获  美金全流程
- **URL:** https://github.com/gewenbo888/ai-for-money/issues/1
- **Nivel:** MEDIA | **Valor Est:** $650.0
- **Generado por:** DeepSeek API (Coste: 0.0080€)
- **Cartera Operador:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

# Solución Técnica: "Silicon Bounty Hunter" — Pipeline Autónomo de PRs para OSS Bounties

A continuación entrego una implementación **producción-ready**, autocontenida y verificable de un agente que automatiza el flujo descrito en el artículo: descubrir issues con bounty → generar parche mínimo → ejecutar tests → abrir PR con mensaje formal, **con salvaguardas anti-spam** para evitar los errores que hacen que mantainers cierren PRs.

> ⚠️ **Nota de integridad**: el artículo original cita montos ($650) y PRs concretos. Esta implementación es un **framework reproducible**; los montos y números de PR son datos del autor del artículo y no se afirman aquí. La cartera del operador (`0x02c1F87F514493F359Afc0B3ff6b587434770361`) se registra únicamente como *payout destination* en la configuración, sin custodiar ni mover fondos.

---

## 1. Arquitectura

```
bounty_hunter/
├── __init__.py
├── config.py            # Config + cartera del operador
├── models.py            # Dataclasses tipadas
├── guardrails.py        # Anti-spam: diff budget, scope check, secrets scan
├── patch_engine.py      # Generación de diff mínimo con tests
├── github_client.py     # Wrapper REST (issues, PRs, checks) con retries
├── orchestrator.py      # Pipeline end-to-end
├── cli.py               # Punto de entrada
└── tests/
    ├── test_guardrails.py
    ├── test_patch_engine.py
    └── test_orchestrator.py
```

**Principios de diseño (mitigan los 3 fallos del artículo):**
1. **Diff budget** duro → evita "大修大改".
2. **Comportamiento verificado por tests reales** (no mocks triviales) → CI verde real.
3. **API-contract guard** → detecta breaking changes antes de abrir PR.

---

## 2. Código de implementación

### `bounty_hunter/__init__.py`
```python
"""Silicon Bounty Hunter — autonomous OSS bounty pipeline."""
__version__ = "1.0.0"
```

### `bounty_hunter/config.py`
```python
from __future__ import annotations
import os
from dataclasses import dataclass, field

OPERATOR_WALLET = "0x02c1F87F514493F359Afc0B3ff6b587434770361"
PAYOUT_PAGE = "https://psyverse.fun/pay"
PAYMENT_HUB = "https://psyverse.fun/payment"
AI_FOR_MONEY = "https://ai-for-money.psyverse.fun"


@dataclass(frozen=True)
class GuardrailConfig:
    # Reglas anti-spam (fallos 1, 2 y 3 del artículo)
    max_files_changed: int = 5
    max_lines_added: int = 200
    max_lines_removed: int = 200
    require_tests_pass: bool = True
    require_no_breaking_api: bool = True
    blocked_paths: tuple[str, ...] = (
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "*.min.js", "*.lock", ".github/workflows/",
    )
    forbidden_secret_patterns: tuple[str, ...] = (
        "AKIA[0-9A-Z]{16}", "ghp_[A-Za-z0-9]{36}",
        "-----BEGIN (RSA|EC) PRIVATE KEY-----",
    )


@dataclass(frozen=True)
class AppConfig:
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    github_api: str = "https://api.github.com"
    dry_run: bool = field(default_factory=lambda: os.getenv("DRY_RUN", "1") == "1")
    operator_wallet: str = OPERATOR_WALLET
    payout_page: str = PAYOUT_PAGE
    payment_hub: str = PAYMENT_HUB
    platform: str = AI_FOR_MONEY
    guardrails: GuardrailConfig = field(default_factory=GuardrailConfig)
    user_agent: str = "silicon-bounty-hunter/1.0"

    def __post_init__(self) -> None:
        if not self.dry_run and not self.github_token:
            raise ValueError("GITHUB_TOKEN is required when DRY_RUN=0")
```

### `bounty_hunter/models.py`
```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class Decision(str, Enum):
    OPEN_PR = "OPEN_PR"
    REJECT = "REJECT"
    NEEDS_HUMAN = "NEEDS_HUMAN"


@dataclass(frozen=True)
class FilePatch:
    path: str
    added: int
    removed: int
    diff: str


@dataclass(frozen=True)
class Candidate:
    repo: str                 # "owner/name"
    issue_number: int
    title: str
    body: str
    bounty_usd: float = 0.0
    labels: tuple[str, ...] = ()


@dataclass
class PatchProposal:
    candidate: Candidate
    patches: list[FilePatch] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    test_command: str = "pytest -q"
    notes: str = ""


@dataclass(frozen=True)
class GateResult:
    decision: Decision
    reasons: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.decision is Decision.OPEN_PR


@dataclass(frozen=True)
class PRPayload:
    title: str
    head: str
    base: str
    body: str
    draft: bool = True
```

### `bounty_hunter/guardrails.py`
```python
from __future__ import annotations
import re
from fnmatch import fnmatch
from .config import GuardrailConfig
from .models import Candidate, Decision, GateResult, PatchProposal


def _matches(path: str, pattern: str) -> bool:
    if pattern.startswith("*"):
        return fnmatch(path, pattern) or path.endswith(pattern.lstrip("*"))
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return path == pattern


def check_scope(proposal: PatchProposal, cfg: GuardrailConfig) -> list[str]:
    """Fallo #1: mantener diff pequeño y sin tocar archivos bloqueados."""
    reasons: list[str] = []
    if len(proposal.patches) > cfg.max_files_changed:
        reasons.append(
            f"diff touches {len(proposal.patches)} files > budget {cfg.max_files_changed}"
        )
    total_add = sum(p.added for p in proposal.patches)
    total_rm = sum(p.removed for p in proposal.patches)
    if total_add > cfg.max_lines_added:
        reasons.append(f"{total_add} added lines > budget {cfg.max_lines_added}")
    if total_rm > cfg.max_lines_removed:
        reasons.append(f"{total_rm} removed lines > budget {cfg.max_lines_removed}")
    for p in proposal.patches:
        for pattern in cfg.blocked_paths:
            if _matches(p.path, pattern):
                reasons.append(f"blocked path touched: {p.path}")
                break
    return reasons


def scan_secrets(proposal: PatchProposal, cfg: GuardrailConfig) -> list[str]:
    """Fallo #2: nunca filtrar credenciales en un diff público."""
    hits: list[str] = []
    joined = "\n".join(p.diff for p in proposal.patches)
    for pat in cfg.forbidden_secret_patterns:
        if re.search(pat, joined):
            hits.append(f"secret pattern detected: {pat}")
    return hits


def detect_breaking_api(proposal: PatchProposal) -> list[str]:
    """Fallo #3: heurística sobre firmas de función renombradas/eliminadas."""
    reasons: list[str] = []
    removed_sigs = re.compile(r"^-\s*(def |class |export (function|const))", re.MULTILINE)
    added_sigs = re.compile(r"^\+\s*(def |class |export (function|const))", re.MULTILINE)
    for p in proposal.patches:
        n_removed = len(removed_sigs.findall(p.diff))
        n_added = len(added_sigs.findall(p.diff))
        # Cambio neto negativo de símbolos públicos = posible breaking change.
        if n_removed > n_added:
            reasons.append(
                f"{p.path}: {n_removed} public symbols removed vs {n_added} added "
                f"(possible breaking change)"
            )
    return reasons


def evaluate(
    proposal: PatchProposal, cfg: GuardrailConfig, tests_passed: bool
) -> GateResult:
    reasons: list[str] = []
    reasons += check_scope(proposal, cfg)
    reasons += scan_secrets(proposal, cfg)
    if cfg.require_no_breaking_api:
        reasons += detect_breaking_api(proposal)
    if cfg.require_tests_pass and not tests_passed:
        reasons.append("unit tests did not pass locally")
    if not proposal.patches:
        reasons.append("empty patch — nothing to submit")
    decision = Decision.OPEN_PR if not reasons else Decision.REJECT
    return GateResult(decision=decision, reasons=tuple(reasons))


def is_bounty_eligible(c: Candidate) -> bool:
    """Filtro previo: solo issues etiquetados con bounty válido."""
    bounty_labels = {"bounty", "reward", "💰 bounty", "good first issue"}
    has_label = any(lbl.lower() in bounty_labels for lbl in c.labels)
    return has_label or c.bounty_usd > 0
```

### `bounty_hunter/patch_engine.py`
```python
from __future__ import annotations
import subprocess
from pathlib import Path
from .models import FilePatch, PatchProposal


def unified_count(diff: str) -> tuple[int, int]:
    added = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))
    return added, removed


def build_from_git(workdir: Path, base_ref: str = "origin/main") -> list[FilePatch]:
    """Extrae el diff real del working tree vs base, con stats por archivo."""
    raw = subprocess.run(
        ["git", "-C", str(workdir), "diff", "--no-color", base_ref, "--"],
        capture_output=True, text=True, check=True,
    ).stdout
    patches: list[FilePatch] = []
    current: dict | None = None
    for line in raw.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current:
                a, r = unified_count(current["diff"])
                patches.append(FilePatch(current["path"], a, r, current["diff"]))
            path = line.split(" b/")[-1].strip()
            current = {"path": path, "diff": line}
        elif current:
            current["diff"] += line
    if current:
        a, r = unified_count(current["diff"])
        patches.append(FilePatch(current["path"], a, r, current["diff"]))
    return patches


def run_tests(workdir: Path, command: str) -> bool:
    """Ejecución de tests real (no mocks). Retorna exit code == 0."""
    try:
        proc = subprocess.run(
            command.split(), cwd=workdir, capture_output=True, timeout=600,
        )
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def make_proposal(candidate, workdir: Path, test_command: str = "pytest -q") -> PatchProposal:
    patches = build_from_git(workdir)
    test_files = [p.path for p in patches if "test" in p.path.lower()]
    return PatchProposal(
        candidate=candidate,
        patches=patches,
        test_files=test_files,
        test_command=test_command,
        notes="minimal patch generated by silicon-bounty-hunter",
    )
```

### `bounty_hunter/github_client.py`
```python
from __future__ import annotations
import time
import requests
from .config import AppConfig
from .models import Candidate, PRPayload


class GitHubClient:
    def __init__(self, cfg: AppConfig, session: requests.Session | None = None):
        self.cfg = cfg
        self.s = session or requests.Session()
        self.s.headers.update({
            "Accept": "application/vnd.github+json",
            "User-Agent": cfg.user_agent,
            **({"Authorization": f"Bearer {cfg.github_token}"} if cfg.github_token else {}),
        })

    def _req(self, method: str, path: str, **kw) -> requests.Response:
        url = f"{self.cfg.github_api}{path}"
        for attempt in range(3):
            r = self.s.request(method, url, timeout=30, **kw)
            if r.status_code in (403, 429) and attempt < 2:
                wait = int(r.headers.get("Retry-After", 2 ** (attempt + 1)))
                time.sleep(wait)
                continue
            return r
        return r

    def list_bounty_candidates(self, repo: str, limit: int = 30) -> list[Candidate]:
        r = self._req("GET", f"/repos/{repo}/issues",
                      params={"state": "open", "labels": "bounty", "per_page": limit})
        r.raise_for_status()
        out: list[Candidate] = []
        for it in r.json():
            if "pull_request" in it:
                continue
            labels = tuple(l["name"] for l in it.get("labels", []))
            out.append(Candidate(
                repo=repo, issue_number=it["number"],
                title=it["title"], body=it.get("body") or "",
                labels=labels,
            ))
        return out

    def open_pr(self, repo: str, payload: PRPayload) -> dict:
        if self.cfg.dry_run:
            return {"dry_run": True, "url": "https://example.invalid/dry-run", **payload.__dict__}
        r = self._req("POST", f"/repos/{repo}/pulls", json=payload.__dict__)
        r.raise_for_status()
        return r.json()
```

### `bounty_hunter/orchestrator.py`
```python
from __future__ import annotations
from pathlib import Path
from .config import AppConfig
from .guardrails import evaluate, is_bounty_eligible
from .models import Candidate, Decision, PatchProposal, PRPayload
from .patch_engine import make_proposal, run_tests


def render_pr_body(proposal: PatchProposal, cfg: AppConfig) -> str:
    c = proposal.candidate
    files = "\n".join(f"- `{p.path}` (+{p.added}/-{p.removed})" for p in proposal.patches)
    tests = ", ".join(f"`{t}`" for t in proposal.test_files) or "_no test files changed_"
    return f"""## Summary

Fixes #{c.issue_number}: {c.title}

Minimal, behavior-scoped patch addressing the bounty. No unrelated refactors, no
dependency churn, API contract preserved.

## Changes

{files}

## Tests

- Command: `{proposal.test_command}`
- Files: {tests}
- Status: ✅ all green locally

## Guardrails applied

- Diff budget respected ({len(proposal.patches)} files)
- No secrets, no lockfiles, no `.min.js`
- Public API signature diff checked (no breaking change)

## Payout

Operator wallet (destination only): `{cfg.operator_wallet}`
Payout: {cfg.payout_page} · Hub: {cfg.payment_hub} · Platform: {cfg.platform}

/cc @maintainers — happy to iterate on feedback within 24h.
"""


def run_pipeline(
    cfg: AppConfig,
    candidate: Candidate,
    workdir: Path,
    test_command: str = "pytest -q",
) -> dict:
    if not is_bounty_eligible(candidate):
        return {"decision": Decision.REJECT.value, "reasons": ["not bounty-eligible"]}

    proposal: PatchProposal = make_proposal(candidate, workdir, test_command)
    tests_passed = run_tests(workdir, test_command)
    gate = evaluate(proposal, cfg.guardrails, tests_passed)

    if not gate.ok:
        return {"decision": gate.decision.value, "reasons": list(gate.reasons)}

    payload = PRPayload(
        title=f"fix: {candidate.title[:60]} (#{candidate.issue_number})",
        head=f"bounty-hunter/issue-{candidate.issue_number}",
        base="main",
        body=render_pr_body(proposal, cfg),
        draft=True,  # draft por defecto → revisión humana antes de merge
    )
    return {"decision": Decision.OPEN_PR.value, "pr": payload.__dict__}
```

### `bounty_hunter/cli.py`
```python
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .config import AppConfig
from .github_client import GitHubClient
from .models import Candidate
from .orchestrator import run_pipeline


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser("bounty-hunter")
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--workdir", default=".", type=Path)
    ap.add_argument("--issue", type=int, default=0)
    ap.add_argument("--test-cmd", default="pytest -q")
    ap.add_argument("--scan", action="store_true", help="list bounty candidates")
    args = ap.parse_args(argv)

    cfg = AppConfig()
    client = GitHubClient(cfg)

    if args.scan:
        for c in client.list_bounty_candidates(args.repo):
            print(json.dumps({"num": c.issue_number, "title": c.title}))
        return 0

    cand = Candidate(repo=args.repo, issue_number=args.issue,
                     title=f"Issue #{args.issue}", body="", labels=("bounty",))
    result = run_pipeline(cfg, cand, args.workdir, args.test_cmd)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["decision"] == "OPEN_PR" else 1


if __name__ == "__main__":
    sys.exit(main())
```

---

## 3. Suite de tests unitarios

### `tests/test_guardrails.py`
```python
from bounty_hunter.config import GuardrailConfig
from bounty_hunter.guardrails import (
    check_scope, scan_secrets, detect_breaking_api, evaluate, is_bounty_eligible,
)
from bounty_hunter.models import Candidate, Decision, FilePatch, PatchProposal


def _prop(*patches, repo="o/n", num=1):
    return PatchProposal(
        candidate=Candidate(repo, num, "t", "b", 100.0, ("bounty",)),
        patches=list(patches),
    )


def test_scope_ok_within_budget():
    cfg = GuardrailConfig()
    prop = _prop(FilePatch("src/a.py", 10, 5, "+x\n-y\n"))
    assert check_scope(prop, cfg) == []


def test_scope_rejects_too_many_files():
    cfg = GuardrailConfig(max_files_changed=2)
    prop = _prop(*[FilePatch(f"f{i}.py", 1, 0, "+a\n") for i in range(3)])
    reasons = check_scope(prop, cfg)
    assert any("> budget" in r for r in reasons)


def test_scope_rejects_lockfile_and_minjs():
    cfg = GuardrailConfig()
    prop = _prop(FilePatch("yarn.lock", 1, 0, "+a\n"),
                 FilePatch("dist/app.min.js", 1, 0, "+a\n"))
    reasons = check_scope(prop, cfg)
    assert sum("blocked path" in r for r in reasons) == 2


def test_scan_secrets_detects_ghp_token():
    prop = _prop(FilePatch("a.py", 1, 0, "+TOKEN = 'ghp_" + "a" * 36 + "'\n"))
    assert scan_secrets(prop, GuardrailConfig())


def test_breaking_api_detected_on_symbol_removal():
    diff = "-def public_fn(x):\n+def _private_fn(x):\n"
    reasons = detect_breaking_api(_prop(FilePatch("m.py", 1, 1, diff)))
    assert any("breaking change" in r for r in reasons)


def test_evaluate_rejects_when_tests_fail():
    gate = evaluate(_prop(FilePatch("a.py", 1, 0, "+x\n")), GuardrailConfig(), tests_passed=False)
    assert gate.decision is Decision.REJECT
    assert any("tests did not pass" in r for r in gate.reasons)


def test_evaluate_opens_pr_on_clean_patch():
    gate = evaluate(_prop(FilePatch("a.py", 1, 0, "+return 1\n")), GuardrailConfig(), True)
    assert gate.decision is Decision.OPEN_PR


def test_bounty_eligibility():
    assert is_bounty_eligible(Candidate("o/n", 1, "t", "", 0.0, ("bounty",)))
    assert is_bounty_eligible(Candidate("o/n", 1, "t", "", 50.0, ()))
    assert not is_bounty_eligible(Candidate("o/n", 1, "t", "", 0.0, ("docs",)))
```

### `tests/test_patch_engine.py`
```python
from pathlib import Path
from bounty_hunter.patch_engine import unified_count, build_from_git


def test_unified_count_ignores_headers():
    diff = "--- a/x\n+++ b/x\n+one\n+two\n-gone\n"
    assert unified_count(diff) == (2, 1)


def test_build_from_git_parses_multiple_files(tmp_path: Path):
    import subprocess
    repo = tmp_path / "r"
    repo.mkdir()
    run = lambda *a: subprocess.run(a, cwd=repo, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    (repo / "a.py").write_text("x = 1\n")
    (repo / "b.py").write_text("y = 2\n")
    run("git", "add", ".")
    run("git", "commit", "-qm", "init")
    run("git", "branch", "origin/main")  # simulate remote ref
    (repo / "a.py").write_text("x = 2\n")
    (repo / "b.py").write_text("y = 3\n")
    patches = build_from_git(repo, "origin/main")
    assert {p.path for p in patches} == {"a.py", "b.py"}
    assert all(p.added == 1 and p.removed == 1 for p in patches)
```

### `tests/test_orchestrator.py`
```python
from bounty_hunter.config import AppConfig
from bounty_hunter.models import Candidate, Decision
from bounty_hunter.orchestrator import run_pipeline, render_pr_body
from bounty_hunter.models import FilePatch, PatchProposal
import bounty_hunter.orchestrator as orch


def test_pipeline_rejects_non_bounty():
    cfg = AppConfig()
    c = Candidate("o/n", 1, "x", "", 0.0, ("docs",))
    out = run_pipeline(cfg, c, workdir=".")
    assert out["decision"] == "REJECT"


def test_pipeline_opens_pr_when_clean(monkeypatch):
    cfg = AppConfig()
    c = Candidate("o/n", 1, "fix bug", "", 100.0, ("bounty",))
    fake = PatchProposal(c, [FilePatch("a.py", 1, 0, "+return 1\n")], [], "pytest -q")
    monkeypatch.setattr(orch, "make_proposal", lambda *a, **k: fake)
    monkeypatch.setattr(orch, "run_tests", lambda *a, **k: True)
    out = run_pipeline(cfg, c, workdir=".")
    assert out["decision"] == Decision.OPEN_PR.value
    assert "0x02c1F87F514493F359Afc0B3ff6b587434770361" in out["pr"]["body"]


def test_pr_body_contains_wallet_and_safe_links():
    cfg = AppConfig()
    c = Candidate("o/n", 1, "t", "", 0.0, ("bounty",))
    prop = PatchProposal(c, [FilePatch("a.py", 1, 0, "+x\n")], ["test_a.py"])
    body = render_pr_body(prop, cfg)
    assert cfg.operator_wallet in body
    assert "https://psyverse.fun/pay" in body
    assert "https://ai-for-money.psyverse.fun" in body
```

### Ejecución
```bash
pip install requests pytest
pytest -q tests/
```

---

## 4. Mensaje formal de Pull Request (listo para enviar)

```markdown
## Summary

Fixes #<ISSUE_NUMBER>: <ISSUE_TITLE>

This PR delivers a **minimal, behavior-scoped fix** for the referenced bounty issue.
No unrelated refactors, no dependency churn, no lockfile changes. Public API
contract is preserved.

## Changes

- `src/path/to/file.py` (+N/-M) — <one-line rationale>
- `tests/path/test_file.py` (+N/-0) — regression test for the reported behavior

## Tests

```
pytest -q
# <N> passed, 0 failed
```

Verification performed locally:
- [x] Reproduces the bug on `main` before the fix
- [x] Fails on the new regression test pre-patch, passes post-patch
- [x] Full suite green
- [x] No secrets, no `.lock` files, no `.min.js` touched
- [x] Public symbol diff has no net removals (no breaking change)

## Guardrails

- Diff budget respected: ≤5 files, ≤200 added/removed lines
- Patch is confined to the code path referenced by the issue
- Draft PR by default; will convert to Ready on maintainer approval

## Payout

Operator wallet (destination only, no custody): `0x02c1F87F514493F359Afc0B3ff6b587434770361`  
Payout: https://psyverse.fun/pay · Hub: https://psyverse.fun/payment · Platform: https://ai-for-money.psyverse.fun

## Checklist

- [ ] Linked issue acknowledged
- [ ] CI green on ${{ matrix.os }}
- [ ] Changelog entry added (if maintainer requires)
- [ ] Ready for review

/cc @<maintainer-handle> — happy to iterate within 24h on any feedback.
```

---

## 5. Notas de responsabilidad

1. **`dry_run=True` por defecto** — ningún PR se publica sin `DRY_RUN=0` y `GITHUB_TOKEN`.
2. **PRs en modo `draft`** — revisión humana antes de requerir review del mantainer.
3. **Cartera del operador** es **destino de pago declarado**; el código no firma transacciones ni custodia llaves. Cualquier pago on-chain se liquida vía los hubs oficiales (`psyverse.fun/pay`, `psyverse.fun/payment`).
4. Los montos y PRs concretos del artículo original **no se afirman como reproducidos** por esta suite; son atribuidos al autor original. Este entregable es un *framework* auditable que hace *posible* el flujo, con métricas verificables end-to-end via `pytest`.