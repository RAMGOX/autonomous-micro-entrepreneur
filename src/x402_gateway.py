"""
Motor 3 — x402 Gateway Oficial (USDC + ETH en Base Mainnet + Protección Anti-Replay y Antigüedad de Bloque):
Monetiza tu activo exclusivo local: Extracción Web Antibot desde IP Residencial (/api/v1/x402/scrape)
y Resolución Técnica (/api/v1/x402/solve), con metadatos compatibles con Coinbase x402 Bazaar.
"""
import os
import re
import sys
import json
import time
import socket
import base64
import ipaddress
from urllib.parse import urlparse
from pathlib import Path
from typing import Dict, Any, Tuple
from web3 import Web3

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from discord_bridge import notify_user_discord

BASE_MAINNET_RPC = "https://mainnet.base.org"
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
USER_PAYOUT_WALLET = os.getenv("USER_PAYOUT_WALLET", "0xdCEa1CDdA6E23Be9670Eda3073691FA6E4e140bf")
PROCESSED_TXS_FILE = BASE_DIR / "memoria" / "estado" / "x402_processed_txs.json"

MAX_TX_AGE_BLOCKS = 1800  # ~1 hora en Base L2 (2s/bloque): bloquea reutilización de TXs históricas

PRICING_TABLE = {
    "scrape": {
        "description": "Clean anti-bot Markdown & metadata extraction from any public URL via residential IP",
        "amount_usdc": 0.01,
        "amount_usdc_units": 10000,  # 6 decimales
        "amount_eth": 0.000005,
        "amount_wei": 5000000000000,
        "amount_usd_est": 0.01
    },
    "solve": {
        "description": "Autonomous code audit, smart contract analysis or data transformation",
        "amount_usdc": 0.10,
        "amount_usdc_units": 100000,
        "amount_eth": 0.00005,
        "amount_wei": 50000000000000,
        "amount_usd_est": 0.10
    },
    "intel": {
        "description": "Curated Base L2 liquidity, token safety & verified developer bounties feed",
        "amount_usdc": 0.02,
        "amount_usdc_units": 20000,
        "amount_eth": 0.00001,
        "amount_wei": 10000000000000,
        "amount_usd_est": 0.02
    }
}


def is_safe_public_url(target_url: str) -> Tuple[bool, str]:
    """Protección estricta Anti-SSRF: impide escanear localhost o la red doméstica del usuario."""
    try:
        parsed = urlparse(target_url.strip())
        if parsed.scheme not in ("http", "https"):
            return False, "Solo se permiten esquemas http:// o https://"
        host = parsed.hostname
        if not host:
            return False, "Host inválido"
        if host.lower() in ("localhost", "0.0.0.0", "metadata.google.internal"):
            return False, "Host local bloqueado por seguridad"

        infos = socket.getaddrinfo(host, None)
        for info in infos:
            ip_str = info[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_reserved
            ):
                return False, "IP privada o reservada bloqueada por seguridad"
        return True, "OK"
    except Exception as e:
        return False, f"No se pudo resolver URL pública: {e}"


def extract_clean_webpage(target_url: str) -> Dict[str, Any]:
    """Extrae contenido limpio en Markdown aprovechando la conexión residencial."""
    ok, reason = is_safe_public_url(target_url)
    if not ok:
        return {"status": "error", "error": reason}

    try:
        import asyncio
        from crawl4ai import AsyncWebCrawler

        async def _crawl():
            async with AsyncWebCrawler(verbose=False) as crawler:
                res = await crawler.arun(url=target_url)
                if res.success and res.markdown:
                    return {"title": res.metadata.get("title", "") if res.metadata else "", "markdown": res.markdown[:12000]}
                return None

        crawled = asyncio.run(_crawl())
        if crawled:
            return {"status": "success", "url": target_url, "engine": "crawl4ai_residential", **crawled}
    except Exception:
        pass

    import requests
    try:
        r = requests.get(
            target_url,
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"}
        )
        title_m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.IGNORECASE | re.DOTALL)
        title = title_m.group(1).strip() if title_m else ""
        clean = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", r.text, flags=re.IGNORECASE | re.DOTALL)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return {"status": "success", "url": target_url, "engine": "http_residential", "title": title, "markdown": clean[:12000]}
    except Exception as e:
        return {"status": "error", "error": str(e)}


class X402Gateway:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(BASE_MAINNET_RPC, request_kwargs={"timeout": 6}))
        self.payout_address = Web3.to_checksum_address(USER_PAYOUT_WALLET)
        self.processed_txs = self._load_processed_txs()

    def _load_processed_txs(self) -> Dict[str, Any]:
        if PROCESSED_TXS_FILE.exists():
            try:
                data = json.loads(PROCESSED_TXS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def get_sales_stats(self) -> Dict[str, Any]:
        txs = self._load_processed_txs()
        total_usd = sum(float(v.get("usd_est", 0.0)) for v in txs.values())
        return {
            "total_calls_paid": len(txs),
            "total_usd_earned": round(total_usd, 4),
            "recent": list(txs.values())[-5:]
        }

    def _save_processed_tx(self, tx_hash: str, payer: str, asset: str, amount: float, usd_est: float, service: str):
        data = self._load_processed_txs()
        data[tx_hash.lower()] = {
            "tx_hash": tx_hash.lower(),
            "payer": payer,
            "asset": asset,
            "amount": amount,
            "usd_est": usd_est,
            "service": service,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.processed_txs = data
        PROCESSED_TXS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROCESSED_TXS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_payment_challenge(self, service: str = "scrape", resource_url: str = "") -> Dict[str, Any]:
        cfg = PRICING_TABLE.get(service, PRICING_TABLE["scrape"])
        return {
            "x402Version": 1,
            "error": "Payment Required",
            "accepts": [
                {
                    "scheme": "exact",
                    "network": "base",
                    "maxAmountRequired": str(cfg["amount_usdc_units"]),
                    "resource": resource_url or f"/api/v1/x402/{service}",
                    "description": cfg["description"],
                    "mimeType": "application/json",
                    "payTo": self.payout_address,
                    "maxTimeoutSeconds": 300,
                    "asset": USDC_BASE_ADDRESS,
                    "extra": {"name": "USD Coin", "version": "2"}
                }
            ],
            "extensions": {
                "bazaar": {
                    "info": {
                        "input": {"service": service, "query": "url or prompt"},
                        "output": {"status": "success", "data": "markdown or json"}
                    }
                }
            },
            "directTxFallback": {
                "network": "base",
                "chainId": 8453,
                "payee": self.payout_address,
                "acceptedAssets": {
                    "USDC": f"{cfg['amount_usdc']} USDC ({USDC_BASE_ADDRESS})",
                    "ETH": f"{cfg['amount_eth']} ETH"
                },
                "header": "X-PAYMENT or X-Payment-Tx: <0x_tx_hash>"
            }
        }

    def extract_tx_hash_from_headers(self, headers) -> str:
        raw = (
            headers.get("X-PAYMENT")
            or headers.get("PAYMENT-SIGNATURE")
            or headers.get("X-Payment-Tx")
            or ""
        ).strip()
        if not raw:
            return ""
        if raw.startswith("0x") and len(raw) == 66:
            return raw
        try:
            decoded = json.loads(base64.b64decode(raw).decode("utf-8"))
            txh = decoded.get("txHash") or decoded.get("payload", {}).get("txHash") or ""
            return str(txh).strip()
        except Exception:
            return raw

    def verify_payment_tx(self, tx_hash: str, service: str = "scrape") -> Tuple[bool, str, Dict[str, Any]]:
        tx_clean = tx_hash.strip().lower()
        if not tx_clean.startswith("0x") or len(tx_clean) != 66:
            return False, "Se requiere un tx_hash válido (0x + 64 hex) en Base Mainnet.", {}

        if tx_clean in self._load_processed_txs():
            return False, "Transacción ya utilizada anteriormente (anti-replay).", {}

        cfg = PRICING_TABLE.get(service, PRICING_TABLE["scrape"])

        try:
            current_block = self.w3.eth.block_number
            rcpt = self.w3.eth.get_transaction_receipt(tx_clean)
            if not rcpt or rcpt.status != 1:
                return False, "Transacción no encontrada o fallida en Base Mainnet.", {}

            # Bloquear reutilización de transacciones históricas antiguas
            if (current_block - rcpt.blockNumber) > MAX_TX_AGE_BLOCKS:
                return False, "Transacción demasiado antigua (>1h). Envía un nuevo micro-pago reciente.", {}

            tx = self.w3.eth.get_transaction(tx_clean)
            payer = tx["from"]
            target_low = self.payout_address.lower()

            # 1. Comprobar pago en USDC (ERC-20 Transfer event)
            for log in rcpt.logs:
                if log.address.lower() == USDC_BASE_ADDRESS.lower() and len(log.topics) >= 3:
                    topic0 = "0x" + log.topics[0].hex().lstrip("0x")
                    if topic0.lower() == TRANSFER_TOPIC:
                        to_logged = "0x" + log.topics[2].hex()[-40:]
                        if to_logged.lower() == target_low:
                            raw_data_hex = log.data.hex() if hasattr(log.data, "hex") else str(log.data)
                            units = int(raw_data_hex, 16)
                            if units >= cfg["amount_usdc_units"]:
                                usdc_amt = units / 1e6
                                self._save_processed_tx(tx_clean, payer, "USDC", usdc_amt, usdc_amt, service)
                                self._notify_sale(service, f"{usdc_amt:.4f} USDC", usdc_amt, payer, tx_clean)
                                return True, "Pago USDC verificado.", {"payer": payer, "asset": "USDC", "amount": usdc_amt, "tx_hash": tx_clean}

            # 2. Comprobar pago en ETH nativo
            if (tx.to or "").lower() == target_low and tx.value >= cfg["amount_wei"]:
                eth_amt = float(self.w3.from_wei(tx.value, "ether"))
                usd_est = round(eth_amt * 2450.0, 4)
                self._save_processed_tx(tx_clean, payer, "ETH", eth_amt, usd_est, service)
                self._notify_sale(service, f"{eth_amt:.6f} ETH", usd_est, payer, tx_clean)
                return True, "Pago ETH verificado.", {"payer": payer, "asset": "ETH", "amount": eth_amt, "tx_hash": tx_clean}

            return False, f"La TX no contiene el pago mínimo a {self.payout_address} ({cfg['amount_usdc']} USDC o {cfg['amount_eth']} ETH).", {}
        except Exception as e:
            return False, f"Error verificando pago en Base RPC: {e}", {}

    def _notify_sale(self, service: str, amount_str: str, usd_est: float, payer: str, tx_hash: str):
        msg = (
            f"⚡ **¡VENTA x402 COBRADA EN TU COINBASE WALLET!**\n\n"
            f"• **Servicio:** `{service.upper()}`\n"
            f"• **Cobrado:** `{amount_str}` (~`${usd_est:.2f} USD`)\n"
            f"• **Cliente:** `{payer}`\n"
            f"• **Tx:** <https://basescan.org/tx/{tx_hash}>"
        )
        notify_user_discord(msg, title="💰 Ingreso Real x402", color=0x2ecc71, channel="general")


_gateway_instance = None


def get_gateway() -> X402Gateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = X402Gateway()
    return _gateway_instance
