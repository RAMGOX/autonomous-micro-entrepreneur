"""
Cloudflare Tunnel Manager + Auto-Sync para Acceso Móvil Permanente:
Cada vez que Cloudflare asigna o renueva el túnel HTTPS, actualiza public_url.json,
sincroniza docs/api_gateway.json a GitHub para que el marcador fijo del móvil
(https://ramgox.github.io/autonomous-micro-entrepreneur/mobile.html) redirija siempre
al Dashboard en vivo sin enlaces rotos, y avisa en Discord #dashboard-24-7.
"""
import os
import re
import sys
import time
import json
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

CLOUDFLARED_BIN = BASE_DIR / "tools" / "cloudflared.exe"
PUBLIC_URL_FILE = BASE_DIR / "memoria" / "estado" / "public_url.json"
DOCS_GATEWAY_FILE = BASE_DIR / "docs" / "api_gateway.json"
ROOT_GATEWAY_FILE = BASE_DIR / "api_gateway.json"
LOCAL_TARGET = "http://127.0.0.1:8080"
PERMANENT_MOBILE_LINK = "https://ramgox.github.io/autonomous-micro-entrepreneur/mobile.html"

try:
    from discord_bridge import notify_user_discord
except Exception:
    notify_user_discord = None


def get_public_url() -> str:
    if PUBLIC_URL_FILE.exists():
        try:
            data = json.loads(PUBLIC_URL_FILE.read_text(encoding="utf-8"))
            return data.get("public_url", "")
        except Exception:
            pass
    return ""


def _sync_gateway_to_github(public_url: str):
    """Publica mobile.html y api_gateway.json directamente en la rama gh-pages sin tocar el árbol de trabajo principal."""
    import tempfile
    tmp_idx = Path(tempfile.gettempdir()) / f"ame_ghpages_idx_{os.getpid()}"
    try:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(tmp_idx)
        if tmp_idx.exists():
            tmp_idx.unlink()

        subprocess.run(["git", "fetch", "origin", "gh-pages"], cwd=str(BASE_DIR), env=env, timeout=20, check=False, capture_output=True)
        base_ref = "origin/gh-pages"
        chk = subprocess.run(["git", "rev-parse", "--verify", base_ref], cwd=str(BASE_DIR), env=env, capture_output=True, text=True)
        parent_sha = chk.stdout.strip() if chk.returncode == 0 else ""

        if parent_sha:
            subprocess.run(["git", "read-tree", parent_sha], cwd=str(BASE_DIR), env=env, check=True, capture_output=True)

        files_to_publish = [
            ("api_gateway.json", DOCS_GATEWAY_FILE),
            ("mobile.html", BASE_DIR / "docs" / "mobile.html"),
        ]
        for target_name, src_path in files_to_publish:
            if src_path.exists():
                blob = subprocess.run(
                    ["git", "hash-object", "-w", str(src_path)],
                    cwd=str(BASE_DIR), env=env, check=True, capture_output=True, text=True
                ).stdout.strip()
                subprocess.run(
                    ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob},{target_name}"],
                    cwd=str(BASE_DIR), env=env, check=True, capture_output=True
                )

        tree_sha = subprocess.run(["git", "write-tree"], cwd=str(BASE_DIR), env=env, check=True, capture_output=True, text=True).stdout.strip()
        cmd_commit = ["git", "commit-tree", tree_sha, "-m", f"chore(mobile): update live gateway {public_url}"]
        if parent_sha:
            cmd_commit.extend(["-p", parent_sha])
        commit_sha = subprocess.run(cmd_commit, cwd=str(BASE_DIR), env=env, check=True, capture_output=True, text=True).stdout.strip()
        subprocess.run(["git", "update-ref", "refs/heads/gh-pages", commit_sha], cwd=str(BASE_DIR), env=env, check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", "gh-pages:gh-pages"], cwd=str(BASE_DIR), timeout=25, check=False, capture_output=True)
    except Exception as e:
        print(f"[Tunnel Git Sync Warning]: {e}")
    finally:
        try:
            if tmp_idx.exists():
                tmp_idx.unlink()
        except Exception:
            pass


def run_tunnel():
    if not CLOUDFLARED_BIN.exists():
        print(f"[Tunnel Error] No se encontró cloudflared en: {CLOUDFLARED_BIN}")
        return

    cmd = [str(CLOUDFLARED_BIN), "tunnel", "--url", LOCAL_TARGET]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    public_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    for line in proc.stdout:
        match = url_pattern.search(line)
        if match and not public_url:
            public_url = match.group(0)
            gateway_data = {
                "status": "online",
                "name": "Autonomous Micro-Entrepreneur (AME v3)",
                "version": "3.0.0",
                "network": "base",
                "chainId": 8453,
                "payee": "0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf",
                "public_url": public_url,
                "mobile_dashboard_url": public_url,
                "permanent_launcher": PERMANENT_MOBILE_LINK,
                "endpoints": {
                    "dashboard": public_url,
                    "pricing": f"{public_url}/api/v1/x402/pricing",
                    "scrape": f"{public_url}/api/v1/x402/scrape",
                    "intel": f"{public_url}/api/v1/x402/intel",
                    "solve": f"{public_url}/api/v1/x402/solve",
                    "agent_manifest": f"{public_url}/.well-known/agent.json",
                    "openapi": f"{public_url}/openapi.json"
                },
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            PUBLIC_URL_FILE.parent.mkdir(parents=True, exist_ok=True)
            DOCS_GATEWAY_FILE.parent.mkdir(parents=True, exist_ok=True)
            json_str = json.dumps(gateway_data, indent=2)
            PUBLIC_URL_FILE.write_text(json_str, encoding="utf-8")
            DOCS_GATEWAY_FILE.write_text(json_str, encoding="utf-8")
            ROOT_GATEWAY_FILE.write_text(json_str, encoding="utf-8")

            _sync_gateway_to_github(public_url)

            if notify_user_discord:
                msg = (
                    f"📱 **Acceso Móvil Directo:** [Abrir Dashboard en el Móvil]({public_url})\n"
                    f"🔖 **Marcador Permanente (nunca caduca):** [Guardar en Inicio del Móvil]({PERMANENT_MOBILE_LINK})\n"
                    f"⚡ **Endpoint x402 Scrape:** `{public_url}/api/v1/x402/scrape`"
                )
                notify_user_discord(msg, title="🌐 Túnel Móvil y Pasarela x402 Sincronizados", color=0x06b6d4, channel="dashboard")

    proc.wait()


if __name__ == "__main__":
    run_tunnel()
