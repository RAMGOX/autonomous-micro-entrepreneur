"""
Cloudflare Tunnel Manager for Autonomous Micro-Entrepreneur.
Exposes port 8080 (Dashboard & x402 Micropayments) securely to the public internet
via official Cloudflare quick tunnels (https://*.trycloudflare.com).
Zero signup, zero credit card, 100% free and encrypted with SSL.
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
LOCAL_TARGET = "http://127.0.0.1:8080"

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

def run_tunnel():
    if not CLOUDFLARED_BIN.exists():
        print(f"[Tunnel Error] No se encontró el binario en: {CLOUDFLARED_BIN}")
        return

    print("=" * 60)
    print("  CLOUDFLARE PUBLIC TUNNEL - PASARELA X402 GLOBAL")
    print(f"  Objetivo Local: {LOCAL_TARGET}")
    print("=" * 60)

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
        print(line.strip())
        match = url_pattern.search(line)
        if match and not public_url:
            public_url = match.group(0)
            print(f"\n[Tunnel OK] ¡URL Pública Activa!: {public_url}\n")
            
            # Guardar en memoria
            PUBLIC_URL_FILE.parent.mkdir(parents=True, exist_ok=True)
            PUBLIC_URL_FILE.write_text(
                json.dumps({
                    "public_url": public_url,
                    "target": LOCAL_TARGET,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "x402_endpoints": {
                        "pricing": f"{public_url}/api/v1/x402/pricing",
                        "intel": f"{public_url}/api/v1/x402/intel",
                        "solve": f"{public_url}/api/v1/x402/solve"
                    }
                }, indent=2),
                encoding="utf-8"
            )

            # Notificar al dashboard
            if notify_user_discord:
                msg = (
                    f"🌐 **PASARELA X402 EXPUESTA AL PÚBLICO GLOBAL**\n\n"
                    f"• **URL Pública:** `{public_url}`\n"
                    f"• **Pricing x402:** `{public_url}/api/v1/x402/pricing`\n"
                    f"• **Inteligencia:** `{public_url}/api/v1/x402/intel`\n"
                    f"• **Resolución de Código:** `{public_url}/api/v1/x402/solve`\n\n"
                    f"Cualquier agente externo en Base L2 puede ahora pagarte micro-transacciones en ETH/USDC."
                )
                notify_user_discord(msg, title="🌐 Pasarela x402 Pública Activa", color=0x2ecc71, channel="dashboard")

    proc.wait()

if __name__ == "__main__":
    run_tunnel()
