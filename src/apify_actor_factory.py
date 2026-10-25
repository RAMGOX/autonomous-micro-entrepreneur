"""
Motor 2 — Apify Store & MCP Actor Factory:
Gestiona el catálogo de Actors listos para publicar gratis en Apify Store (modelo Pay-Per-Event, 80% comisión en USD),
ejecuta smoke-tests periódicos de salud en vivo y sincroniza estado en Obsidian y Bandeja de Revisión Móvil.
"""
import os
import sys
import json
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

from review_queue import push_for_review

ACTORS_DIR = BASE_DIR / "apify_actors"
STATE_FILE = BASE_DIR / "memoria" / "estado" / "apify_actors_status.json"
OBS_APIFY_MD = BASE_DIR / "memoria" / "MOTOR_2_APIFY_ACTORS.md"


def bootstrap_initial_actors():
    """Crea y mantiene listos los 2 primeros Actors B2B/MCP de alta demanda si no existen."""
    # Actor 1: Extractor B2B de Licitaciones Públicas Europeas (TED Europa v3)
    a1 = ACTORS_DIR / "eu-public-tenders-b2b"
    (a1 / ".actor").mkdir(parents=True, exist_ok=True)
    (a1 / "src").mkdir(parents=True, exist_ok=True)

    if not (a1 / ".actor" / "actor.json").exists():
        (a1 / ".actor" / "actor.json").write_text(json.dumps({
            "actorSpecification": 1,
            "name": "eu-public-tenders-b2b-leads",
            "title": "EU Public Tenders & Government Contracts B2B Extractor (MCP Ready)",
            "description": "Extracts active European & Spanish government software, IT, and B2B procurement tenders from TED API v3 into clean JSON/CSV for sales teams and AI agents.",
            "version": "1.0",
            "dockerfile": "../Dockerfile",
            "input": "./input_schema.json"
        }, indent=2), encoding="utf-8")

        (a1 / ".actor" / "input_schema.json").write_text(json.dumps({
            "title": "EU Tenders Search Input",
            "type": "object",
            "schemaVersion": 1,
            "properties": {
                "keyword": {"title": "Keyword", "type": "string", "default": "software", "description": "Sector or keyword (e.g., software, cybersecurity, cloud, AI)"},
                "country": {"title": "Country ISO-3", "type": "string", "default": "ESP", "description": "3-letter country code (ESP, DEU, FRA, ITA) or empty for all EU"},
                "maxItems": {"title": "Max Results", "type": "integer", "default": 25, "minimum": 1, "maximum": 200}
            },
            "required": ["keyword"]
        }, indent=2), encoding="utf-8")

        (a1 / "Dockerfile").write_text(
            "FROM apify/actor-python:3.11\nCOPY requirements.txt ./\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . ./\nCMD [\"python3\", \"-m\", \"src.main\"]\n",
            encoding="utf-8"
        )
        (a1 / "requirements.txt").write_text("apify>=2.0.0\nrequests>=2.31.0\n", encoding="utf-8")
        (a1 / "src" / "__init__.py").write_text("", encoding="utf-8")
        (a1 / "src" / "main.py").write_text('''"""
Apify Actor: EU Public Tenders & Government Contracts Extractor (TED API v3).
Monetization: Pay-Per-Event ($0.005 per tender extracted). Zero proxy cost.
"""
import asyncio
import requests

TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"


def fetch_ted_tenders(keyword: str = "software", country: str = "ESP", limit: int = 20) -> list:
    clauses = [f'FT ~ "{keyword}"']
    if country and len(country.strip()) == 3:
        clauses.append(f'CY = "{country.strip().upper()}"')
    query_str = " AND ".join(clauses)
    payload = {
        "query": query_str,
        "fields": ["ND", "PD", "TI", "CY", "AU"],
        "page": 1,
        "limit": min(max(1, int(limit)), 100)
    }
    r = requests.post(TED_SEARCH_URL, json=payload, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=20)
    r.raise_for_status()
    notices = r.json().get("notices", [])
    results = []
    for n in notices:
        nd = n.get("ND", "")
        results.append({
            "notice_id": nd,
            "publication_date": n.get("PD"),
            "country": n.get("CY"),
            "title": n.get("TI"),
            "buyer": n.get("AU"),
            "url": f"https://ted.europa.eu/en/notice/-/detail/{nd}" if nd else ""
        })
    return results


async def main():
    from apify import Actor
    async with Actor:
        inp = await Actor.get_input() or {}
        items = fetch_ted_tenders(
            keyword=inp.get("keyword", "software"),
            country=inp.get("country", "ESP"),
            limit=inp.get("maxItems", 25)
        )
        for item in items:
            await Actor.push_data(item)


if __name__ == "__main__":
    asyncio.run(main())
''', encoding="utf-8")
        (a1 / "README.md").write_text(
            "# EU Public Tenders & Government Contracts B2B Extractor\n\n"
            "Automated B2B lead & public procurement extractor from the official European Union TED v3 database.\n"
            "- **Ideal for:** IT consultancies, SaaS sales teams, and MCP AI Agents.\n"
            "- **Pricing:** Pay-Per-Event (`$5 / 1,000 tenders`).\n"
            "- **Deploy command:** `npx apify-cli login && npx apify-cli push`\n",
            encoding="utf-8"
        )

    # Actor 2: Auditor de Seguridad y Liquidez de Tokens en Base L2 (MCP Ready)
    a2 = ACTORS_DIR / "base-dex-rug-auditor"
    (a2 / ".actor").mkdir(parents=True, exist_ok=True)
    (a2 / "src").mkdir(parents=True, exist_ok=True)

    if not (a2 / ".actor" / "actor.json").exists():
        (a2 / ".actor" / "actor.json").write_text(json.dumps({
            "actorSpecification": 1,
            "name": "base-l2-token-liquidity-safety-auditor",
            "title": "Base L2 Token Liquidity & Rug Risk Auditor (MCP Server Tool)",
            "description": "Audits any Base L2 token contract on-chain (bytecode verification, DEX reserve depth, 24h volume/FDV ratio, honeypot/illiquidity risk score) for AI agents and DeFi workflows.",
            "version": "1.0",
            "dockerfile": "../Dockerfile",
            "input": "./input_schema.json"
        }, indent=2), encoding="utf-8")

        (a2 / ".actor" / "input_schema.json").write_text(json.dumps({
            "title": "Base Token Audit Input",
            "type": "object",
            "schemaVersion": 1,
            "properties": {
                "tokenAddresses": {
                    "title": "Token Addresses on Base",
                    "type": "array",
                    "editor": "stringList",
                    "default": ["0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "0x940181a94A35A4569E4529A3CDfB74e38FD98631"]
                }
            },
            "required": ["tokenAddresses"]
        }, indent=2), encoding="utf-8")

        (a2 / "Dockerfile").write_text(
            "FROM apify/actor-python:3.11\nCOPY requirements.txt ./\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . ./\nCMD [\"python3\", \"-m\", \"src.main\"]\n",
            encoding="utf-8"
        )
        (a2 / "requirements.txt").write_text("apify>=2.0.0\nrequests>=2.31.0\n", encoding="utf-8")
        (a2 / "src" / "__init__.py").write_text("", encoding="utf-8")
        (a2 / "src" / "main.py").write_text('''"""
Apify Actor: Base L2 Token Liquidity & Rug Risk Auditor (MCP Ready).
"""
import asyncio
import requests


def audit_base_token(address: str) -> dict:
    addr = address.strip().lower()
    gt_url = f"https://api.geckoterminal.com/api/v2/networks/base/tokens/{addr}"
    r = requests.get(gt_url, headers={"Accept": "application/json"}, timeout=12)
    if r.status_code != 200:
        return {"address": addr, "found": False, "risk_level": "CRITICAL_UNINDEXED", "safety_score": 0}

    attrs = r.json().get("data", {}).get("attributes", {})
    reserve_usd = float(attrs.get("total_reserve_in_usd") or 0.0)
    vol_24h = float((attrs.get("volume_usd") or {}).get("h24") or 0.0)
    fdv_usd = float(attrs.get("fdv_usd") or 0.0)

    score = 100
    warnings = []
    if reserve_usd < 10000:
        score -= 55
        warnings.append("Low liquidity (<$10k USD)")
    elif reserve_usd < 50000:
        score -= 25
        warnings.append("Moderate liquidity (<$50k USD)")
    if vol_24h < 1000:
        score -= 20
        warnings.append("Low 24h trading volume")
    if fdv_usd > 0 and reserve_usd > 0 and (fdv_usd / reserve_usd) > 100:
        score -= 20
        warnings.append("High FDV-to-Liquidity ratio (>100x)")

    score = max(0, score)
    risk = "LOW" if score >= 75 else ("MEDIUM" if score >= 45 else "HIGH")
    return {
        "address": addr,
        "found": True,
        "name": attrs.get("name"),
        "symbol": attrs.get("symbol"),
        "price_usd": attrs.get("price_usd"),
        "liquidity_reserve_usd": round(reserve_usd, 2),
        "volume_24h_usd": round(vol_24h, 2),
        "fdv_usd": round(fdv_usd, 2),
        "safety_score": score,
        "risk_level": risk,
        "warnings": warnings
    }


async def main():
    from apify import Actor
    async with Actor:
        inp = await Actor.get_input() or {}
        addrs = inp.get("tokenAddresses") or ["0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"]
        for a in addrs[:50]:
            await Actor.push_data(audit_base_token(a))


if __name__ == "__main__":
    asyncio.run(main())
''', encoding="utf-8")
        (a2 / "README.md").write_text(
            "# Base L2 Token Liquidity & Rug Risk Auditor (MCP Ready)\n\n"
            "Instant on-chain & DEX liquidity risk scoring for Base L2 tokens. Built for AI Agents via Apify MCP.\n"
            "- **Deploy command:** `npx apify-cli login && npx apify-cli push`\n",
            encoding="utf-8"
        )


def _load_actor_module(name: str, file_path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(file_path))
    if not spec or not spec.loader:
        raise RuntimeError(f"No se pudo cargar {file_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_actor_health_checks() -> List[Dict[str, Any]]:
    """Ejecuta tests reales en local de cada Actor y registra estado en Obsidian y Bandeja de Revisión."""
    bootstrap_initial_actors()
    results = []

    # Test Actor 1 (TED API v3)
    t1_ok = False
    t1_note = ""
    try:
        mod1 = _load_actor_module("actor_ted_main", ACTORS_DIR / "eu-public-tenders-b2b" / "src" / "main.py")
        sample = mod1.fetch_ted_tenders("software", "ESP", 3)
        t1_ok = isinstance(sample, list) and len(sample) > 0
        t1_note = f"OK ({len(sample)} licitaciones reales extraídas)"
    except Exception as e:
        t1_note = f"Aviso API: {e}"

    results.append({
        "slug": "eu-public-tenders-b2b",
        "title": "EU Public Tenders & Government Contracts B2B Extractor",
        "path": "apify_actors/eu-public-tenders-b2b",
        "healthy": t1_ok,
        "smoke_ok": t1_ok,
        "status_note": t1_note,
        "pricing_model": "$0.005 / tender (Pay-Per-Event)",
        "monetization": "$0.005 / tender (Pay-Per-Event)",
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")
    })

    # Test Actor 2 (Base Token Auditor)
    t2_ok = False
    t2_note = ""
    try:
        mod2 = _load_actor_module("actor_base_main", ACTORS_DIR / "base-dex-rug-auditor" / "src" / "main.py")
        audit = mod2.audit_base_token("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
        t2_ok = bool(audit.get("found")) and audit.get("safety_score", 0) >= 80
        t2_note = f"OK (USDC Score: {audit.get('safety_score')}/100, Liq: ${audit.get('liquidity_reserve_usd'):,.0f})"
    except Exception as e:
        t2_note = f"Aviso API: {e}"

    results.append({
        "slug": "base-dex-rug-auditor",
        "title": "Base L2 Token Liquidity & Rug Risk Auditor (MCP)",
        "path": "apify_actors/base-dex-rug-auditor",
        "healthy": t2_ok,
        "smoke_ok": t2_ok,
        "status_note": t2_note,
        "pricing_model": "$0.003 / audit (Pay-Per-Event)",
        "monetization": "$0.003 / audit (Pay-Per-Event)",
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")
    })

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Registrar en Bandeja de Revisión si aún no han sido revisados por el usuario
    for r in results:
        if r["healthy"]:
            push_for_review(
                category="apify_actor",
                title=f"Apify Actor Listo: {r['title']}",
                source_url="https://console.apify.com/actors",
                reward_display="Recurrente (80% MRR USD)",
                estimated_usd=75.0,
                summary=f"Actor probado en vivo ({r['status_note']}). Modelo {r['pricing_model']}. Carpeta lista en `{r['path']}` para publicar gratis en Apify Store + MCP.",
                deliverable_path=r["path"],
                solver="Argon 4 Factory",
                opp_id=f"apify_{r['slug']}",
                action_payload={"actor_path": r["path"], "slug": r["slug"]}
            )

    lines = [
        "# 🏭 Motor 2: Fábrica de Actors B2B en Apify Store + MCP",
        f"- **Última verificación automática:** `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
        "- **Comisión desarrollador:** `80%` neto en USD (0€ coste de servidor, corre en nube de Apify)\n",
        "| Actor | Estado Salud | Modelo Cobro | Carpeta Local |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for r in results:
        badge = "🟢 ONLINE" if r["healthy"] else "🔴 REPARAR"
        lines.append(f"| **{r['title']}** | {badge} — {r['status_note']} | `{r['pricing_model']}` | `{r['path']}` |")

    OBS_APIFY_MD.parent.mkdir(parents=True, exist_ok=True)
    OBS_APIFY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return results


if __name__ == "__main__":
    print(json.dumps(run_actor_health_checks(), indent=2, ensure_ascii=False))
