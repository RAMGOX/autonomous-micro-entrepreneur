"""
Motor 1 — GitHub & Algora Bounty Hunter:
Escanea issues abiertos reales con recompensa en USD ($25 - $2,500) en GitHub (Algora, Opire y etiquetas Bounty),
filtra repositorios fantasma o saturados de competidores, y encola solo oportunidades limpias de código.
"""
import os
import re
import sys
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))
load_dotenv(BASE_DIR / "config" / ".env")

from opportunity_queue import push_opportunity

SEEN_GH_FILE = BASE_DIR / "memoria" / "estado" / "github_bounties_vistas.json"
OBS_GH_MD = BASE_DIR / "memoria" / "MOTOR_1_BOUNTIES_GITHUB.md"

SEARCH_QUERIES = [
    'is:issue is:open label:"💎 Bounty" comments:<=18 no:assignee sort:created-desc',
    'is:issue is:open "algora.io" comments:<=18 no:assignee sort:created-desc',
    'is:issue is:open "opire.dev" comments:<=18 no:assignee sort:created-desc',
    'is:issue is:open "[BOUNTY]" "$" comments:<=18 no:assignee sort:created-desc'
]

ALLOWED_TECH_HINTS = [
    "python", "typescript", "javascript", "node", "react", "nextjs", "solidity",
    "evm", "api", "cli", "scraper", "mcp", "sdk", "json", "fastapi", "bot", "html", "css", "sql"
]

HEAVY_AVOID_HINTS = [
    "rust", "solana anchor", "c++", "kernel", "fpga", "cuda", "zig", "haskell", "nix", "scala"
]


def _extract_usd_reward(title: str, body: str, labels: List[str]) -> float:
    combined = " | ".join([title] + labels + [body[:800]])
    matches = re.findall(r"\$\s*([0-9]{2,4}(?:,[0-9]{3})?)", combined)
    vals = []
    for m in matches:
        try:
            v = float(m.replace(",", ""))
            if 20.0 <= v <= 3000.0:
                vals.append(v)
        except Exception:
            pass
    return max(vals) if vals else 0.0


def _load_seen() -> set:
    if SEEN_GH_FILE.exists():
        try:
            return set(json.loads(SEEN_GH_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def _save_seen(seen: set):
    SEEN_GH_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_GH_FILE.write_text(json.dumps(sorted(list(seen))[-500:], indent=2), encoding="utf-8")


def _resolve_github_token() -> str:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token and token != "TU_GITHUB_TOKEN_AQUI":
        return token
    try:
        import subprocess
        out = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=str(BASE_DIR),
            encoding="utf-8",
            creationflags=0x08000000
        ).strip()
        m = re.search(r":(ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)@github\.com", out)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""


def scan_github_bounties(max_enqueue: int = 6) -> List[Dict[str, Any]]:
    token = _resolve_github_token()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AME-BountyRadar/3.0"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    seen = _load_seen()
    found_summary = []
    repo_enqueued_counts: Dict[str, int] = {}
    enqueued = 0
    now_utc = datetime.now(timezone.utc)

    for q in SEARCH_QUERIES:
        url = f"https://api.github.com/search/issues?q={urllib.parse.quote(q)}&per_page=20"
        data = None
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) and "Authorization" in headers:
                headers.pop("Authorization", None)
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=12) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                except Exception:
                    continue
            else:
                continue
        except Exception:
            continue
        time.sleep(1.2)
        if not data:
            continue

        for item in data.get("items", []):
            html_url = item.get("html_url", "")
            if not html_url or "/pull/" in html_url:
                continue

            # Ignorar issues con demasiados comentarios (>18 suele significar 5+ personas ya compitiendo)
            comments_count = int(item.get("comments", 0))
            if comments_count > 18:
                continue

            # Verificar frescura (< 45 días sin actividad = descartar repo fantasma)
            updated_str = item.get("updated_at", "")
            if updated_str:
                try:
                    dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    if (now_utc - dt).days > 45:
                        continue
                except Exception:
                    pass

            title = item.get("title", "")
            t_low_clean = title.strip().lower()
            # Descartar falsas issues abiertas por bots externos o agregadores de alertas
            if t_low_clean.startswith(("claiming ", "claim bounty", "[claim]", "submission:", "bounty claim")) or "bounty alert" in t_low_clean:
                continue
            body = item.get("body") or ""
            labels = [lb.get("name", "") for lb in item.get("labels", []) if isinstance(lb, dict)]
            usd = _extract_usd_reward(title, body, labels)
            if usd < 25.0:
                continue

            text_low = f"{title} {' '.join(labels)} {body[:1000]} {html_url}".lower()
            if any(bad in text_low for bad in HEAVY_AVOID_HINTS) and not any(ok in text_low for ok in ("python", "typescript", "javascript")):
                continue

            repo_match = re.search(r"github\.com/([^/]+/[^/]+)/issues/([0-9]+)", html_url)
            repo_slug = repo_match.group(1) if repo_match else "github"

            entry_info = {
                "repo": repo_slug,
                "title": title,
                "url": html_url,
                "usd": usd,
                "comments": comments_count,
                "updated": updated_str[:10]
            }
            if not any(x["url"] == html_url for x in found_summary):
                found_summary.append(entry_info)

            if html_url not in seen and enqueued < max_enqueue and repo_enqueued_counts.get(repo_slug, 0) < 2:
                diff = "alta" if usd >= 250 else ("media" if usd >= 75 else "baja")
                push_opportunity(
                    title=f"[GH ${int(usd)}] {repo_slug}: {title}",
                    url=html_url,
                    description=f"Repo: {repo_slug} | Comentarios actuales: {comments_count}\nLabels: {', '.join(labels)}\n\n{body[:1200]}",
                    difficulty=diff,
                    estimated_value_usd=usd,
                    reward_currency=f"${int(usd)} USD",
                    is_escrow_verified=("algora" in text_low or "💎" in " ".join(labels) + title),
                    source="github_bounty"
                )
                seen.add(html_url)
                repo_enqueued_counts[repo_slug] = repo_enqueued_counts.get(repo_slug, 0) + 1
                enqueued += 1

    _save_seen(seen)
    found_summary.sort(key=lambda x: x["usd"], reverse=True)

    # Actualizar panel limpio en Obsidian
    lines = [
        "# 🎯 Motor 1: Radar de Bounties de Código en GitHub (Algora / Opire)",
        f"- **Último escaneo:** `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- **Candidatos activos filtrados:** `{len(found_summary)}` (sin asignado, repo vivo, `>= $25 USD`)",
        "- **Regla anti-baneo:** El sistema analiza y prepara borrador en local; **tú apruebas en Discord** antes de enviar PR.\n",
        "| Recompensa | Repositorio | Issue | Competencia | Enlace |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    for b in found_summary[:25]:
        clean_t = b["title"].replace("|", "-").strip()[:65]
        lines.append(f"| **`${int(b['usd'])}`** | `{b['repo']}` | {clean_t} | `{b['comments']}` com. | [Abrir Issue]({b['url']}) |")

    OBS_GH_MD.parent.mkdir(parents=True, exist_ok=True)
    OBS_GH_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return found_summary


if __name__ == "__main__":
    res = scan_github_bounties()
    print(f"[GitHub Bounty Hunter] {len(res)} bounties reales detectados.")
