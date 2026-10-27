"""
Apify Actor: Global Software Vulnerability & CVE Radar (GitHub Advisory MCP).
Monetization: Pay-Per-Event ($0.003 per vulnerability record). Zero proxy cost.
"""
import asyncio
import requests

GITHUB_ADVISORIES_URL = "https://api.github.com/advisories"


def fetch_security_advisories(ecosystem: str = "pip", severity: str = "high", limit: int = 20) -> list:
    params = {"per_page": min(max(1, int(limit)), 100)}
    if ecosystem and ecosystem.lower() != "all":
        params["ecosystem"] = ecosystem.lower().strip()
    if severity and severity.lower() != "all":
        params["severity"] = severity.lower().strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AdvisoryRadar/1.0"
    }
    r = requests.get(GITHUB_ADVISORIES_URL, params=params, headers=headers, timeout=15)
    r.raise_for_status()
    raw = r.json()
    results = []
    for adv in raw:
        vulns = adv.get("vulnerabilities", [])
        affected_pkgs = []
        for v in vulns:
            pkg = v.get("package", {}) if isinstance(v, dict) else {}
            first_patched = v.get("first_patched_version") if isinstance(v, dict) else None
            patched_str = first_patched.get("identifier") if isinstance(first_patched, dict) else str(first_patched) if first_patched else None
            affected_pkgs.append({
                "ecosystem": pkg.get("ecosystem"),
                "name": pkg.get("name"),
                "vulnerable_version_range": v.get("vulnerable_version_range") if isinstance(v, dict) else None,
                "first_patched_version": patched_str
            })
        cve_id = adv.get("cve_id")
        results.append({
            "ghsa_id": adv.get("ghsa_id"),
            "cve_id": cve_id,
            "summary": adv.get("summary"),
            "severity": adv.get("severity"),
            "published_at": adv.get("published_at"),
            "updated_at": adv.get("updated_at"),
            "html_url": adv.get("html_url"),
            "affected_packages": affected_pkgs
        })
    return results


async def main():
    from apify import Actor
    async with Actor:
        inp = await Actor.get_input() or {}
        items = fetch_security_advisories(
            ecosystem=inp.get("ecosystem", "pip"),
            severity=inp.get("severity", "high"),
            limit=inp.get("maxItems", 20)
        )
        for item in items:
            await Actor.push_data(item)


if __name__ == "__main__":
    asyncio.run(main())
